#!/usr/bin/env python3
"""
规则同步脚本
从上游拉取规则 → 合并自定义补充 → 输出 .list / .yaml / .mrs 三种格式
所有文件按规则名分文件夹：rules/{name}/
"""

import os
import sys
import shutil
import subprocess
import yaml
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.yaml")
RULES_DIR = os.path.join(ROOT_DIR, "rules")

MIHOMO_BIN = os.environ.get("MIHOMO_BIN", shutil.which("mihomo") or "mihomo")

RAW_BASE = "https://raw.githubusercontent.com"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_raw_url(repo, branch, path):
    return f"{RAW_BASE}/{repo}/{branch}/{path}"


def download_file(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mokka-rules-sync/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
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


def compile_mrs(clash_yaml_path, mrs_output_path, rule_name):
    if not shutil.which(MIHOMO_BIN) and MIHOMO_BIN == "mihomo":
        print(f"    mihomo not found, skip MRS")
        return False

    os.makedirs(os.path.dirname(mrs_output_path), exist_ok=True)
    try:
        subprocess.run(
            [MIHOMO_BIN, "convert-ruleset", "classical", "yaml",
             clash_yaml_path, mrs_output_path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        print(f"    MRS ok")
        return True
    except FileNotFoundError:
        print(f"    mihomo not found, skip MRS")
        return False
    except subprocess.CalledProcessError as e:
        print(f"    MRS failed ({rule_name}): {e.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        print(f"    MRS timeout ({rule_name})")
        return False


def sync_rules():
    config = load_config()
    upstream_configs = config.get("upstream", {})
    rules = config.get("rules", [])

    if not rules:
        print("No rules in config.yaml")
        return

    stats = {"updated": 0, "unchanged": 0, "failed": 0, "mrs_compiled": 0, "mrs_skipped": 0}

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
        loon_path = rule.get("loon_path")
        if loon_path:
            loon_url = build_raw_url(repo, branch, loon_path)
            loon_out = os.path.join(rule_dir, f"{name}.list")

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

        # Clash → rules/{name}/{name}.yaml
        clash_path = rule.get("clash_path")
        if clash_path:
            clash_url = build_raw_url(repo, branch, clash_path)
            clash_out = os.path.join(rule_dir, f"{name}.yaml")

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

        # MRS → rules/{name}/{name}.mrs
        clash_out = os.path.join(rule_dir, f"{name}.yaml")
        if os.path.exists(clash_out):
            mrs_out = os.path.join(rule_dir, f"{name}.mrs")
            if compile_mrs(clash_out, mrs_out, name):
                stats["mrs_compiled"] += 1
            else:
                stats["mrs_skipped"] += 1

    print(f"\n{'=' * 50}")
    print(f"Done! updated={stats['updated']} unchanged={stats['unchanged']} "
          f"failed={stats['failed']} mrs={stats['mrs_compiled']}")

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    sync_rules()
