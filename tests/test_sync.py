import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


spec = importlib.util.spec_from_file_location(
    "rule_sync", Path(__file__).resolve().parents[1] / "scripts" / "sync.py"
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class RuleConversionTests(unittest.TestCase):
    def test_geosite_preserves_exact_and_suffix_matching(self):
        self.assertEqual(
            sync.extract_metacubex_rules("# comment\n+.x.com\napi.example.com\n"),
            ["DOMAIN-SUFFIX,x.com", "DOMAIN,api.example.com"],
        )

    def test_geoip_handles_both_families_without_dns_resolution(self):
        self.assertEqual(
            sync.extract_metacubex_ip_rules(
                "# comment\n\n104.244.42.0/24\n2606:1f80:f000::/36\n"
            ),
            [
                "IP-CIDR,104.244.42.0/24,no-resolve",
                "IP-CIDR6,2606:1f80:f000::/36,no-resolve",
            ],
        )

    def test_geoip_rejects_invalid_or_misaligned_networks(self):
        for entry in ["not-a-network", "104.244.42.1/24", "2606:1f80:f000::/129"]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                sync.extract_metacubex_ip_rules(entry)


class MixedSourceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rule_dir = self.root / "xAI"
        self.rule_dir.mkdir()
        (self.rule_dir / "custom.list").write_text(
            "# Duplicate upstream entry and one additional host\n"
            "DOMAIN-SUFFIX,x.com\nDOMAIN-SUFFIX,grokbot.com\n"
        )
        self.sources = {
            "geo/geosite/x.list": "+.x.com\n+.grok.com\n",
            "geo/geosite/cursor.list": "+.cursor.com\n+.cursorvm.com\n",
            "geo/geoip/twitter.list": "104.244.42.0/24\n2606:1f80:f000::/36\n",
        }
        self.config = {
            "upstream": {"metacubex": {"repo": "example/rules", "branch": "meta"}},
            "rules": [{"name": "xAI", "upstream": "metacubex", "paths": list(self.sources)}],
        }

    def run_sync(self):
        def download(url):
            return self.sources[url.split("/meta/", 1)[1]]

        with patch.object(sync, "RULES_DIR", str(self.root)), \
                patch.object(sync, "load_config", return_value=self.config), \
                patch.object(sync, "download_file", side_effect=download), \
                contextlib.redirect_stdout(io.StringIO()):
            sync.sync_rules("xAI")

    def output_bytes(self):
        return {suffix: (self.rule_dir / ("xAI." + suffix)).read_bytes()
                for suffix in ("list", "yaml")}

    def test_mixed_sources_generate_equal_formats_and_preserve_unrelated_sets(self):
        untouched = self.root / "unrelated.list"
        untouched.write_text("unchanged\n")
        self.run_sync()
        loon = sync.extract_loon_rules((self.rule_dir / "xAI.list").read_text())
        clash = yaml.safe_load((self.rule_dir / "xAI.yaml").read_text())["payload"]
        self.assertEqual(loon, clash)
        self.assertEqual(loon, [
            "DOMAIN-SUFFIX,x.com", "DOMAIN-SUFFIX,grok.com",
            "DOMAIN-SUFFIX,cursor.com", "DOMAIN-SUFFIX,cursorvm.com",
            "IP-CIDR,104.244.42.0/24,no-resolve",
            "IP-CIDR6,2606:1f80:f000::/36,no-resolve",
            "DOMAIN-SUFFIX,grokbot.com",
        ])
        self.assertEqual(untouched.read_text(), "unchanged\n")

    def test_failed_invalid_or_empty_source_preserves_both_outputs(self):
        self.run_sync()
        before = self.output_bytes()
        for content in [None, "invalid-cidr\n", "# no networks\n"]:
            with self.subTest(content=content):
                self.sources["geo/geoip/twitter.list"] = content
                with self.assertRaises(SystemExit) as error:
                    self.run_sync()
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(self.output_bytes(), before)

    def test_empty_domain_source_does_not_publish_a_partial_collection(self):
        self.run_sync()
        before = self.output_bytes()
        self.sources["geo/geosite/x.list"] = "# no domains\n"
        with self.assertRaises(SystemExit):
            self.run_sync()
        self.assertEqual(self.output_bytes(), before)


class LocalSourceAndOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.meta_dir = self.root / "MetaAI"
        self.meta_dir.mkdir()
        self.meta_source = self.meta_dir / "custom.list"
        self.meta_source.write_text(
            "DOMAIN-SUFFIX,meta.ai\nDOMAIN-SUFFIX,muse.ai\n"
            "DOMAIN-SUFFIX,metaaivm.com\nDOMAIN-SUFFIX,metaaiusercontent.com\n"
            "DOMAIN-SUFFIX,auth.meta.com\nDOMAIN-SUFFIX,meta.ai\n"
        )
        self.other_dir = self.root / "AIOther"
        self.other_dir.mkdir()
        (self.other_dir / "custom.list").write_text("DOMAIN-SUFFIX,muse.ai\n")
        self.upstream = (
            "+.meta.ai\napi.meta.ai\n+.muse.ai\n+.metaaivm.com\n"
            "+.metaaiusercontent.com\n+.notmeta.ai\n+.other.ai\n"
            "+.meta.ai.unrelated.example\n"
        )
        self.other_config = {
            "name": "AIOther", "upstream": "metacubex",
            "paths": ["geo/geosite/category-ai-!cn.list"],
        }
        self.config = {
            "upstream": {"metacubex": {"repo": "example/rules", "branch": "meta"}},
            "rules": [
                {"name": "Meta AI", "slug": "MetaAI", "source": "local"},
                self.other_config,
            ],
        }

    def run_sync(self, only):
        with patch.object(sync, "RULES_DIR", str(self.root)), \
                patch.object(sync, "load_config", return_value=self.config), \
                patch.object(sync, "download_file", return_value=self.upstream) as download, \
                contextlib.redirect_stdout(io.StringIO()):
            sync.sync_rules(only)
        return download

    def output_bytes(self, slug):
        return {suffix: (self.root / slug / (slug + "." + suffix)).read_bytes()
                for suffix in ("list", "yaml")}

    def payload(self, slug):
        loon = sync.extract_loon_rules((self.root / slug / (slug + ".list")).read_text())
        clash = yaml.safe_load((self.root / slug / (slug + ".yaml")).read_text())["payload"]
        self.assertEqual(loon, clash)
        return loon

    def test_local_source_generates_both_formats_without_network(self):
        download = self.run_sync("MetaAI")
        download.assert_not_called()
        self.assertEqual(self.payload("MetaAI"), [
            "DOMAIN-SUFFIX,meta.ai", "DOMAIN-SUFFIX,muse.ai",
            "DOMAIN-SUFFIX,metaaivm.com", "DOMAIN-SUFFIX,metaaiusercontent.com",
            "DOMAIN-SUFFIX,auth.meta.com",
        ])

    def test_empty_local_source_preserves_published_outputs(self):
        self.run_sync("MetaAI")
        before = self.output_bytes("MetaAI")
        self.meta_source.write_text("# temporarily empty\n")
        with self.assertRaises(SystemExit):
            self.run_sync("MetaAI")
        self.assertEqual(self.output_bytes("MetaAI"), before)

    def test_migration_is_opt_in_and_keeps_legacy_domains(self):
        self.run_sync("AIOther")
        self.assertEqual(self.payload("AIOther"),
                         sync.extract_metacubex_rules(self.upstream))

    def test_enabled_exclusion_removes_owned_domains_and_new_subdomains(self):
        self.other_config["exclude_custom_from"] = ["MetaAI"]
        self.run_sync("AIOther")
        self.assertEqual(self.payload("AIOther"), [
            "DOMAIN-SUFFIX,notmeta.ai", "DOMAIN-SUFFIX,other.ai",
            "DOMAIN-SUFFIX,meta.ai.unrelated.example",
        ])

    def test_invalid_owner_preserves_both_fallback_outputs(self):
        self.run_sync("AIOther")
        before = self.output_bytes("AIOther")
        self.other_config["exclude_custom_from"] = ["MetaAI"]
        for source in ["# empty\n", "IP-CIDR,192.0.2.0/24,no-resolve\n"]:
            with self.subTest(source=source):
                self.meta_source.write_text(source)
                with self.assertRaises(SystemExit):
                    self.run_sync("AIOther")
                self.assertEqual(self.output_bytes("AIOther"), before)


if __name__ == "__main__":
    unittest.main()
