#!/usr/bin/env bash
# ============================================
# CMFA 配置加密 + 推送脚本
# 用法: bash scripts/encrypt-cmfa.sh
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MIHOMO="$ROOT_DIR/tools/mihomo.exe"
CONFIG_DIR="$ROOT_DIR/configs/cmfa"
SOURCE="$CONFIG_DIR/cmfa-config.yml"
OUTPUT="$CONFIG_DIR/cmfa-config.yml.age"
KEY_FILE="$CONFIG_DIR/keys/oneplus12.pub"

if [ ! -f "$SOURCE" ]; then
    echo "找不到配置文件: $SOURCE"
    exit 1
fi

if [ ! -f "$KEY_FILE" ]; then
    echo "找不到公钥文件: $KEY_FILE"
    exit 1
fi

PUBLIC_KEY=$(grep '^age1' "$KEY_FILE")
if [ -z "$PUBLIC_KEY" ]; then
    echo "公钥文件格式错误"
    exit 1
fi

echo "=== CMFA 配置加密 ==="
echo "源文件: $SOURCE"
echo "公钥: oneplus12 (mlkem768-x25519)"
echo ""

"$MIHOMO" age encrypt "$PUBLIC_KEY" "$SOURCE" "$OUTPUT"
echo "加密完成: $OUTPUT"
echo "文件大小: $(wc -c < "$OUTPUT") bytes"
echo ""

cd "$ROOT_DIR"
git add configs/cmfa/cmfa-config.yml.age
git diff --cached --quiet && { echo "没有变化，无需推送"; exit 0; }

git commit -m "update: CMFA encrypted config"
git push origin main
echo ""
echo "推送完成!"
echo "CMFA 拉取地址: https://raw.githubusercontent.com/zgwtm/flux/main/configs/cmfa/cmfa-config.yml.age"
