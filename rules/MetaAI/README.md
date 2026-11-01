# Meta AI

Service rules for Meta AI, Muse, their connection and content domains, and Meta
account authentication. The authentication suffix is shared with other Meta
products; Facebook, Instagram, and shared CDN domains are not included wholesale.

`custom.list` is the single maintained source. The `source: local` configuration
generates matching `MetaAI.list` (Loon) and `MetaAI.yaml` (Mihomo classical) files:

```sh
python scripts/sync.py --only MetaAI
```

Load MetaAI before AI payment, shared infrastructure, and broad AI fallback rules.
The routing policy and its allowed outbound choices are configured by each client.

## Routing ownership

Clients using Meta AI or Muse must subscribe to this dedicated set. AIOther and
ai-common do not provide compatibility entries for these services.

AIOther enables `exclude_custom_from: [MetaAI]` in `config.yaml`. During each sync,
the synchronizer excludes exact hosts and suffixes owned by this source, including
new upstream subdomains, without changing unrelated AI services. Empty or
unsupported ownership sources stop generation and preserve the existing outputs.
