# flux

Network filtering rule sets curated from upstream sources and synchronized daily.

## Usage

### Loon

Add a remote rule set using its `.list` URL, then assign a routing policy:

```text
https://raw.githubusercontent.com/zgwtm/flux/main/rules/Claude/Claude.list
```

### Clash / Mihomo

Add the rule provider and select a policy in your client's `rules` section:

```yaml
rule-providers:
  claude:
    type: http
    behavior: classical
    url: "https://raw.githubusercontent.com/zgwtm/flux/main/rules/Claude/Claude.yaml"
    path: ./ruleset/Claude.yaml
    interval: 86400
```

Replace `Claude` in the URL with another rule directory and matching filename.

## Maintaining Rules

- `config.yaml` defines upstream sources and generated rule sets.
- `rules/<slug>/custom.list` adds rules to a generated set.
- `scripts/sync.py` combines upstream and custom rules, removes duplicates in
  first-seen order, and writes both `.list` and `.yaml` outputs.
- `rules/Typeless/` and `rules/_global/` are maintained manually and are not
  changed by the sync script.

A rule's `slug` fixes its directory and filenames independently of its display
name. Without a `slug`, the script uses `name` for both.

Edit the configuration or a custom list rather than generated files. To sync
locally with Python and PyYAML installed:

```sh
python scripts/sync.py
python scripts/sync.py --only GoogleSuite
```

For manual rule sets, maintain each supported format directly. The Mihomo
`udp-leak.yaml` also blocks UDP port 443 with an `AND` rule; the Loon `.list`
contains only the shared STUN/TURN port rules.

## Sync Schedule

GitHub Actions is scheduled daily at 20:00 UTC (04:00 UTC+8). It also runs manually
or after changes to `config.yaml` or `rules/**/custom.list` on `main`. Scheduled
runs may start later than the configured time.

The workflow commits changed rule files to `main`, which is used by the
subscription URLs above. Timestamp-only changes do not create a new commit.

## Encrypted Artifacts

`configs/cmfa/` contains an age-encrypted client configuration artifact. Plaintext
configuration and private keys are kept outside this repository.

## Contributors

- [zgwtm](https://github.com/zgwtm) - Project maintainer.
- **GPT-6 Astra** - AI assistance with English documentation and comment cleanup.
