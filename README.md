# Metadata catalog contracts

Schemas and standard-library Python tooling for immutable catalog releases.
Applications pin repository commits, archive bytes/checksums and source-manifest
checksums. Source releases preserve existing IDs, aliases and SKU URIs.

| Tool | Purpose |
| --- | --- |
| `catalog-release.py inventory` | List allowlisted application source inputs |
| `catalog-release.py pack` | Pack an immutable per-vertical archive |
| `catalog-release.py resolve` | Verify archives in a content-addressed cache |
| `catalog-release.py hydrate` | Materialize the application's exact source pins |
| `catalog-release.py verify-workspace` | Check hydrated files against their manifests |
| `validate-normalized.py export.json` | Validate explicit public export envelopes |

```sh
python3 catalog-release.py hydrate --workspace /path/to/app --lock /path/to/app/catalog.lock.json --cache /tmp/catalog-cache
python3 catalog-release.py verify-workspace --workspace /path/to/app --lock /path/to/app/catalog.lock.json
```

Private release downloads require authenticated GitHub CLI access. The resolver
checks archive safety, ownership, schema versions, byte limits and hashes.
Hydration rejects unsafe paths and incomplete registry coverage. It does not
activate production; runtime artifacts include only checked source files.

Transport schemas do not certify normalized legacy rows or public-export rights.
Normalized exports must preserve identities, namespace references, reject ambiguous
aliases/dangling targets and include metadata/media permission evidence. Alias
uniqueness is scoped to vertical and entity kind. `fixtures/original.json` is
synthetic CC0 data; it does not relicense upstream catalogs.

Code is MIT licensed. Upstream data, images and trademarks retain separate rights.
See [Contributing](CONTRIBUTING.md) and the
[application catalog workflow](https://github.com/metadata-fyi/metadata/blob/main/docs/CATALOG-REPOSITORIES.md).
