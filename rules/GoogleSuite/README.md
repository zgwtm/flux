# Google Suite

A combined rule set for routing Gemini, YouTube and Google services through one
policy in Loon or Clash/Mihomo. The separate service rule sets remain available
for clients that need different policies.

## Sources

The `GoogleSuite` entry in `config.yaml` merges these MetaCubeX geosite lists in
order:

1. `google-gemini.list`
2. `youtube.list`
3. `google.list`
4. Local additions from `custom.list`

The sync script keeps the first occurrence of each rule. The `GoogleSuite` slug
keeps the directory and subscription URLs stable independently of the display
name.

## Subscription URLs

- [Loon](https://raw.githubusercontent.com/zgwtm/flux/main/rules/GoogleSuite/GoogleSuite.list)
- [Clash / Mihomo](https://raw.githubusercontent.com/zgwtm/flux/main/rules/GoogleSuite/GoogleSuite.yaml)

Assign the rule set to your preferred routing policy in the client.
