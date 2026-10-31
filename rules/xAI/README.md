# xAI

Combined rules for X/Twitter, xAI/Grok, Cursor and Grok Bot.

The sync job merges these MetaCubeX sources and `custom.list`:

- `geo/geosite/x.list`: X/Twitter and Grok domains.
- `geo/geosite/cursor.list`: Cursor APIs, assets and hosted computers.
- `geo/geoip/twitter.list`: Twitter IPv4 and IPv6 ranges.

`custom.list` adds the Grok Bot entry point, shared account/content hosts and
Cursor's dedicated download bucket. SpaceX/Starlink websites and Tesla are
outside this set's scope; `spacex.ai` is included for account authentication.

Both generated formats contain the same ordered, deduplicated rules:

- `xAI.yaml`: Mihomo **classical** rule provider, YAML format.
- `xAI.list`: Loon rule list.

CIDR entries use `no-resolve` to avoid resolving unrelated domains solely for
an IP match. Load this set before broad AI and international fallback rules.
Shared third-party services such as Stripe and Auth0 remain separate.

```yaml
rule-providers:
  xAI:
    type: http
    behavior: classical
    format: yaml
    url: https://raw.githubusercontent.com/zgwtm/flux/main/rules/xAI/xAI.yaml
    path: ./ruleset/xAI.yaml
    interval: 86400

rules:
  - RULE-SET,xAI,xAI
```

The final `xAI` in the rule is a client-defined policy group. Generate updates
with `python scripts/sync.py --only xAI`; edit sources or `custom.list`, not the
generated files. A failed, invalid or empty source leaves existing outputs
unchanged.
