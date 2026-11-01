# Metadata catalog contracts

Version 1 defines independent catalog source releases. Each vertical owns its
source files, contribution review and asset permissions. Applications pin a full
repository commit, artifact checksum and source-manifest checksum in a lockfile.
No submodules or runtime Git clones are required.

`catalog-release.py inventory` inspects runtime source imports and the explicit
TCG shard list. It excludes raw snapshots, review captures, runtime databases,
service accounts and image binaries. `pack` creates an immutable per-vertical
archive. `resolve` verifies it into a content-addressed cache without activating it.

The JSON schemas document the transport contract. The Python resolver enforces
archive safety, schema versions, repository ownership, pins, byte limits and
source hashes. It uses the authenticated GitHub CLI for private releases. The
schemas do not imply that existing legacy rows meet a new normalized entity
schema. Preserve existing IDs, aliases and SKU URIs during migration.

Code in this repository is MIT licensed. This license does not license upstream
data, card artwork, manufacturer photography or trademarks. Every redistributable
record and image needs separate permission evidence. See `CONTRIBUTING.md`.

`validate-normalized.py export.json` checks explicit public export envelopes:
preserved legacy IDs, namespaced references, alias ambiguity, relationship targets,
metadata permission and media permission evidence. An approved field is a review
assertion, not an automatically inferred license grant. `fixtures/original.json`
is synthetic original data dedicated to the public domain (CC0-1.0). No existing
upstream corpus is relicensed by this example.

Application workspaces can hydrate exact pins without Git submodules:

```sh
python3 catalog-release.py hydrate --workspace /path/to/app --lock /path/to/app/catalog.lock.json --cache /tmp/catalog-cache --artifact-directory /path/to/verified-archives
python3 catalog-release.py verify-workspace --workspace /path/to/app --lock /path/to/app/catalog.lock.json
```

Hydration preserves existing identical files, rejects unsafe paths and requires
complete registry coverage. Application source inputs must be generated rather
than tracked copies. Runtime artifact preparation includes only checked source
files; raw vertical review captures are excluded. Alias uniqueness is scoped to
the vertical and entity kind, even when a preserved legacy ID contains slashes.
