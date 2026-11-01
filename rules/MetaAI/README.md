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

## Migration

Existing Meta AI and Muse entries remain in AIOther and ai-common for clients that
have not yet added this set. A client loading MetaAI earlier will already use its
dedicated policy. After all affected clients have migrated:

1. Enable `exclude_custom_from: [MetaAI]` on the AIOther entry in `config.yaml`.
   The synchronizer then excludes exact hosts and suffixes owned by this source,
   including new upstream subdomains, without changing unrelated AI services.
2. Remove the legacy Muse entries from `AIOther/custom.list` and both manually
   maintained ai-common formats.
3. Regenerate AIOther and verify both formats before publishing the cleanup.

Do not activate the cleanup while older client configurations still rely on those
entries. Empty or unsupported ownership sources stop generation and preserve the
existing outputs.
