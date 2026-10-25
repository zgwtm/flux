#!/usr/bin/env python3
"""
Merge upstream and custom rules into Loon and Clash/Mihomo rule sets.
Output paths use rules/{slug}/, with the rule name as the default slug.
"""

import argparse
import os
import re
import sys
import time
import yaml
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.yaml")
RULES_DIR = os.path.join(ROOT_DIR, "rules")

RAW_BASE = "https://raw.githubusercontent.com"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_raw_url(repo, branch, path):
    return f"{RAW_BASE}/{repo}/{branch}/{path}"


def download_file(url, retries=2, delay=3):
    for attempt in range(1 + retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "flux-rules-sync/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {url}")
            return None
        except Exception as e:
            if attempt < retries:
                print(f"  Retry {attempt + 1}/{retries} after error: {e}")
                time.sleep(delay)
            else:
                print(f"  Error (gave up after {1 + retries} attempts): {e}")
                return None


def file_md5(content):
    return hashlib.md5(content.encode("utf-8")).hexdigest()


UPDATED_LINE_PATTERN = re.compile(r"^# Updated: .*$", re.MULTILINE)


def content_fingerprint(content):
    """Ignore generated timestamps when comparing content.

    Other header changes still count, so source and rule metadata stay current.
    """
    return file_md5(UPDATED_LINE_PATTERN.sub("# Updated: -", content))


def read_existing(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def add_sync_header(content, rule_name, upstream_url):
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst).strftime("%Y-%m-%d %H:%M:%S CST")
    header = (
        f"# Synced by flux-rules\n"
        f"# Rule: {rule_name}\n"
        f"# Source: {upstream_url}\n"
        f"# Updated: {now}\n"
        f"#\n"
    )
    return header + content


def read_custom_rules(name):
    custom_path = os.path.join(RULES_DIR, name, "custom.list")
    if not os.path.exists(custom_path):
        return []
    with open(custom_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    rules = [line.strip() for line in lines
             if line.strip() and not line.strip().startswith("#")]
    if rules:
        print(f"  + {len(rules)} custom rules")
    return rules


def append_custom_to_loon(loon_content, custom_rules):
    separator = (
        "\n"
        "# Custom rules\n"
    )
    return loon_content.rstrip("\n") + separator + "\n".join(custom_rules) + "\n"


def append_custom_to_clash(clash_content, custom_rules):
    separator = "  # Custom rules\n"
    custom_lines = "\n".join(f"  - {rule}" for rule in custom_rules)
    return clash_content.rstrip("\n") + "\n" + separator + custom_lines + "\n"


def extract_clash_rules(content):
    """Extract rules from a Clash payload, omitting comments and its header."""
    rules = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s == "payload:":
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        rules.append(s)
    return rules


def extract_loon_rules(content):
    """Extract Loon rules, omitting comments and blank lines."""
    rules = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rules.append(s)
    return rules


def extract_metacubex_rules(content):
    """Convert MetaCubeX geosite entries into rules shared by both formats.

    Prefix '+.' becomes DOMAIN-SUFFIX; other entries become DOMAIN rules.
    """
    rules = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("+."):
            rules.append(f"DOMAIN-SUFFIX,{s[2:]}")
        else:
            rules.append(f"DOMAIN,{s}")
    return rules


def write_if_changed(path, content, label, rule_count, source_count, stats):
    """Write only substantive changes, ignoring generated timestamps."""
    existing = read_existing(path)
    if existing and content_fingerprint(existing) == content_fingerprint(content):
        print(f"  {label} unchanged")
        stats["unchanged"] += 1
    else:
        write_file(path, content)
        print(f"  {label} updated ({source_count} sources -> {rule_count} rules)")
        stats["updated"] += 1


def dedup_preserve(seq):
    """Remove duplicates while preserving first-seen order."""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def resolve_rule_slug(rule):
    """Resolve the output slug, which must be a single safe path component."""
    name = rule["name"]
    slug = rule.get("slug", name)
    if not isinstance(slug, str) or not slug.strip() or slug != slug.strip():
        raise ValueError(f"rule {name!r} has an empty or invalid slug")
    if (
        slug in {".", ".."}
        or os.path.basename(slug) != slug
        or "/" in slug
        or "\\" in slug
    ):
        raise ValueError(f"rule {name!r} has an unsafe slug: {slug!r}")
    return slug


def download_and_merge(repo, branch, paths, fmt):
    """Download and merge sources in the requested format.

    Return (rules, source_urls), or (None, []) if any source download fails.
    """
    all_rules = []
    sources = []
    for p in paths:
        url = build_raw_url(repo, branch, p)
        content = download_file(url)
        if content is None:
            return None, []
        if fmt == "clash":
            all_rules += extract_clash_rules(content)
        elif fmt == "metacubex":
            all_rules += extract_metacubex_rules(content)
        else:
            all_rules += extract_loon_rules(content)
        sources.append(url)
    return all_rules, sources


def sync_rules(only=None):
    config = load_config()
    upstream_configs = config.get("upstream", {})
    rules = config.get("rules", [])

    if not rules:
        print("No rules in config.yaml")
        return

    resolved_rules = []
    seen_slugs = set()
    for rule in rules:
        slug = resolve_rule_slug(rule)
        if slug in seen_slugs:
            raise ValueError(f"duplicate rule slug: {slug!r}")
        seen_slugs.add(slug)
        resolved_rules.append((rule, slug))

    if only:
        resolved_rules = [
            (rule, slug)
            for rule, slug in resolved_rules
            if rule["name"] == only or slug == only
        ]
        if not resolved_rules:
            print(f"Rule not found: {only}", file=sys.stderr)
            sys.exit(2)

    stats = {"updated": 0, "unchanged": 0, "failed": 0}

    print(f"Syncing {len(resolved_rules)} rules...")
    print("=" * 50)

    for rule, slug in resolved_rules:
        name = rule["name"]
        upstream_name = rule["upstream"]
        upstream_cfg = upstream_configs.get(upstream_name)

        if not upstream_cfg:
            print(f"\n[{name}] upstream not found: {upstream_name}")
            stats["failed"] += 1
            continue

        repo = upstream_cfg["repo"]
        branch = upstream_cfg["branch"]

        rule_dir = os.path.join(RULES_DIR, slug)
        os.makedirs(rule_dir, exist_ok=True)

        print(f"\n[{name}] {rule.get('description', '')}")

        custom_rules = read_custom_rules(slug)

        # Generate both formats from one merged, deduplicated source sequence.
        # Legacy format-specific sources are handled below.
        mc_paths = rule.get("paths")
        if mc_paths:
            merged, sources = download_and_merge(repo, branch, mc_paths, "metacubex")
            if merged is None:
                stats["failed"] += 1
                continue
            merged = dedup_preserve(merged + custom_rules)
            source_label = " + ".join(sources)

            loon_body = "\n".join(merged) + "\n"
            write_if_changed(
                os.path.join(rule_dir, f"{slug}.list"),
                add_sync_header(loon_body, name, source_label),
                ".list", len(merged), len(sources), stats,
            )

            clash_body = "payload:\n" + "\n".join(f"  - {r}" for r in merged) + "\n"
            write_if_changed(
                os.path.join(rule_dir, f"{slug}.yaml"),
                add_sync_header(clash_body, name, source_label),
                ".yaml", len(merged), len(sources), stats,
            )
            continue

        # Legacy Loon sources.
        loon_out = os.path.join(rule_dir, f"{slug}.list")
        loon_paths = rule.get("loon_paths")
        loon_path = rule.get("loon_path")
        if loon_paths:
            merged, sources = download_and_merge(repo, branch, loon_paths, "loon")
            if merged is not None:
                merged = dedup_preserve(merged + custom_rules)
                body = "\n".join(merged) + "\n"
                content_with_header = add_sync_header(body, name, " + ".join(sources))
                existing = read_existing(loon_out)
                if existing and content_fingerprint(existing) == content_fingerprint(content_with_header):
                    print(f"  .list unchanged")
                    stats["unchanged"] += 1
                else:
                    write_file(loon_out, content_with_header)
                    print(f"  .list updated (merged {len(sources)} sources -> {len(merged)} rules)")
                    stats["updated"] += 1
            else:
                stats["failed"] += 1
        elif loon_path:
            loon_url = build_raw_url(repo, branch, loon_path)
            content = download_file(loon_url)
            if content:
                content_with_header = add_sync_header(content, name, loon_url)
                if custom_rules:
                    content_with_header = append_custom_to_loon(content_with_header, custom_rules)
                existing = read_existing(loon_out)
                if existing and content_fingerprint(existing) == content_fingerprint(content_with_header):
                    print(f"  .list unchanged")
                    stats["unchanged"] += 1
                else:
                    write_file(loon_out, content_with_header)
                    print(f"  .list updated")
                    stats["updated"] += 1
            else:
                stats["failed"] += 1

        # Legacy Clash/Mihomo sources.
        clash_out = os.path.join(rule_dir, f"{slug}.yaml")
        clash_paths = rule.get("clash_paths")
        clash_path = rule.get("clash_path")
        if clash_paths:
            merged, sources = download_and_merge(repo, branch, clash_paths, "clash")
            if merged is not None:
                merged = dedup_preserve(merged + custom_rules)
                body = "payload:\n" + "\n".join(f"  - {r}" for r in merged) + "\n"
                content_with_header = add_sync_header(body, name, " + ".join(sources))
                existing = read_existing(clash_out)
                if existing and content_fingerprint(existing) == content_fingerprint(content_with_header):
                    print(f"  .yaml unchanged")
                    stats["unchanged"] += 1
                else:
                    write_file(clash_out, content_with_header)
                    print(f"  .yaml updated (merged {len(sources)} sources -> {len(merged)} rules)")
                    stats["updated"] += 1
            else:
                stats["failed"] += 1
        elif clash_path:
            clash_url = build_raw_url(repo, branch, clash_path)
            content = download_file(clash_url)
            if content:
                content_with_header = add_sync_header(content, name, clash_url)
                if custom_rules:
                    content_with_header = append_custom_to_clash(content_with_header, custom_rules)
                existing = read_existing(clash_out)
                if existing and content_fingerprint(existing) == content_fingerprint(content_with_header):
                    print(f"  .yaml unchanged")
                    stats["unchanged"] += 1
                else:
                    write_file(clash_out, content_with_header)
                    print(f"  .yaml updated")
                    stats["updated"] += 1
            else:
                stats["failed"] += 1

    print(f"\n{'=' * 50}")
    print(f"Done! updated={stats['updated']} unchanged={stats['unchanged']} "
          f"failed={stats['failed']}")

    if stats["failed"] > 0:
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Synchronize rule sets")
    parser.add_argument(
        "--only",
        metavar="NAME_OR_SLUG",
        help="sync only the specified rule display name or slug",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sync_rules(args.only)
