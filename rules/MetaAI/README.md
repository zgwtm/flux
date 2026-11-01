# Meta AI

Rules for Meta AI, Muse, Meta account and Graph services, Facebook, and shared
Meta content delivery. This set also routes matching traffic from other Meta
products; its scope is broader than AI services alone.

## Scope

The maintained source contains eight domain suffixes:

- AI services and content: `meta.ai`, `muse.ai`, `metaaivm.com`, and
  `metaaiusercontent.com`.
- Meta accounts and Graph services: `meta.com`, including `auth.meta.com`,
  `accountscenter.meta.com`, and their subdomains.
- Facebook and shared content delivery: `facebook.com`, `fbcdn.net`, and
  `fbsbx.com`. This includes matching Facebook website and media traffic.

Instagram-specific domains such as `instagram.com` and `cdninstagram.com` are
not included. Shared Meta domains may still be used by Instagram or other products.

## Generation

`custom.list` is the single maintained source. The `source: local` configuration
generates matching `MetaAI.list` (Loon) and `MetaAI.yaml` (Mihomo classical) files:

```sh
python scripts/sync.py --only MetaAI
python scripts/sync.py --only AIOther
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
