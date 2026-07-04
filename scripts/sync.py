#!/usr/bin/env python3
"""
规则同步脚本
从上游拉取规则 → 合并自定义补充 → 输出 .list / .yaml 两种格式
所有文件按规则名分文件夹：rules/{name}/
"""

import os
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
            req = urllib.request.Request(url, headers={"User-Agent": "mokka-rules-sync/1.0"})
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
        f"# Synced by mokka-rules\n"
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
        "# ========== Mokka 的补充规则 ==========\n"
    )
    return loon_content.rstrip("\n") + separator + "\n".join(custom_rules) + "\n"


def append_custom_to_clash(clash_content, custom_rules):
    separator = "  # ========== Mokka 的补充规则 ==========\n"
    custom_lines = "\n".join(f"  - {rule}" for rule in custom_rules)
    return clash_content.rstrip("\n") + "\n" + separator + custom_lines + "\n"


def extract_clash_rules(content):
    """从 Clash payload(yaml) 内容里提取纯规则行，丢掉注释和 'payload:' 头。"""
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
    """从 Loon(.list) 内容里提取纯规则行，丢掉注释和空行。"""
    rules = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rules.append(s)
    return rules


def dedup_preserve(seq):
    """去重，但保留首次出现的顺序。"""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def download_and_merge(repo, branch, paths, fmt):
    """下载多个上游路径并按 fmt('clash'/'loon') 提取规则后合并。
    任一路径下载失败返回 (None, [])；否则返回 (rules_list, source_urls)。"""
    all_rules = []
    sources = []
    for p in paths:
        url = build_raw_url(repo, branch, p)
        content = download_file(url)
        if content is None:
            return None, []
        if fmt == "clash":
            all_rules += extract_clash_rules(content)
        else:
            all_rules += extract_loon_rules(content)
        sources.append(url)
    return all_rules, sources


def sync_rules():
    config = load_config()
    upstream_configs = config.get("upstream", {})
    rules = config.get("rules", [])

    if not rules:
        print("No rules in config.yaml")
        return

    stats = {"updated": 0, "unchanged": 0, "failed": 0}

    print(f"Syncing {len(rules)} rules...")
    print("=" * 50)

    for rule in rules:
        name = rule["name"]
        upstream_name = rule["upstream"]
        upstream_cfg = upstream_configs.get(upstream_name)

        if not upstream_cfg:
            print(f"\n[{name}] upstream not found: {upstream_name}")
            stats["failed"] += 1
            continue

        repo = upstream_cfg["repo"]
        branch = upstream_cfg["branch"]

        rule_dir = os.path.join(RULES_DIR, name)
        os.makedirs(rule_dir, exist_ok=True)

        print(f"\n[{name}] {rule.get('description', '')}")

        custom_rules = read_custom_rules(name)

        # Loon → rules/{name}/{name}.list
        loon_out = os.path.join(rule_dir, f"{name}.list")
        loon_paths = rule.get("loon_paths")
        loon_path = rule.get("loon_path")
        if loon_paths:
            merged, sources = download_and_merge(repo, branch, loon_paths, "loon")
            if merged is not None:
                merged = dedup_preserve(merged + custom_rules)
                body = "\n".join(merged) + "\n"
                content_with_header = add_sync_header(body, name, " + ".join(sources))
                existing = read_existing(loon_out)
                if existing and file_md5(existing) == file_md5(content_with_header):
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
                if existing and file_md5(existing) == file_md5(content_with_header):
                    print(f"  .list unchanged")
                    stats["unchanged"] += 1
                else:
                    write_file(loon_out, content_with_header)
                    print(f"  .list updated")
                    stats["updated"] += 1
            else:
                stats["failed"] += 1

        # Clash/Mihomo → rules/{name}/{name}.yaml
        clash_out = os.path.join(rule_dir, f"{name}.yaml")
        clash_paths = rule.get("clash_paths")
        clash_path = rule.get("clash_path")
        if clash_paths:
            merged, sources = download_and_merge(repo, branch, clash_paths, "clash")
            if merged is not None:
                merged = dedup_preserve(merged + custom_rules)
                body = "payload:\n" + "\n".join(f"  - {r}" for r in merged) + "\n"
                content_with_header = add_sync_header(body, name, " + ".join(sources))
                existing = read_existing(clash_out)
                if existing and file_md5(existing) == file_md5(content_with_header):
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
                if existing and file_md5(existing) == file_md5(content_with_header):
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


if __name__ == "__main__":
    sync_rules()
