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


if __name__ == "__main__":
    unittest.main()
