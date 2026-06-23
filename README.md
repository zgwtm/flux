# flux

Personal network filtering rules — curated from upstream sources, auto-synced daily.

## Structure

```
config.yaml              ← 规则清单（改这里加规则）
scripts/sync.py          ← 同步脚本
rules/
├── Claude/
│   ├── custom.list      ← 自定义补充规则（编辑这个）
│   ├── Claude.list      ← Loon 格式（自动生成）
│   └── Claude.yaml      ← Clash/Mihomo 格式（自动生成）
├── OpenAI/
│   └── ...
└── _global/
    └── udp-leak.list    ← UDP 防泄露规则
```

## Usage

### Loon

```
https://raw.githubusercontent.com/zgwtm/flux/main/rules/{RuleName}/{RuleName}.list
```

### Clash / Mihomo

```yaml
rule-providers:
  claude:
    type: http
    behavior: classical
    url: "https://raw.githubusercontent.com/zgwtm/flux/main/rules/Claude/Claude.yaml"
    path: ./ruleset/Claude.yaml
    interval: 86400
```

## Adding Rules

Edit `config.yaml` or `rules/{name}/custom.list`, push — GitHub Actions handles the rest.

## Sync Schedule

Daily at UTC 20:00 (CST 04:00). Also triggers on `config.yaml` or `custom.list` changes.
