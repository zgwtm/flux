# GameDownload

A combined rule set for Steam traffic and game download CDNs. To route matching
traffic directly, assign it to `DIRECT`:

```text
RULE-SET,GameDownload,DIRECT
```

The Steam source includes store, community and API traffic as well as downloads.
The custom PlayStation entries cover downloads and system updates, not PSN
account or store traffic.

## Sources

The `GameDownload` entry in `config.yaml` combines these MetaCubeX geosite lists:

- `steam.list`
- `category-game-platforms-download.list`

The sync script appends `custom.list`, removes duplicates in first-seen order,
and generates both `.list` and `.yaml` files from the same rule sequence.

## Custom Additions

- `steamserver.net`: Steam download CDN coverage.
- `steamcontent.com`: Explicit Steam content coverage, deduplicated if upstream
  also includes the rule.
- `dl.playstation.net`: PlayStation game downloads, including subdomains.
- `ps5.update.playstation.net`: PS5 system update downloads.

## Subscription URLs

- [Loon](https://raw.githubusercontent.com/zgwtm/flux/main/rules/GameDownload/GameDownload.list)
- [Clash / Mihomo](https://raw.githubusercontent.com/zgwtm/flux/main/rules/GameDownload/GameDownload.yaml)
