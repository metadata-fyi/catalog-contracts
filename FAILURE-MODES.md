# Catalog release failure modes

Before implementation, the acceptance scenarios are:

- An artifact or source file changes after pinning: reject before installation.
- A release is absent, truncated, oversized, or has an unexpected schema: reject.
- Archive paths escape the cache, duplicate files, contain links, or hide unlisted content: reject.
- A branch name substitutes for a full commit, a duplicate vertical appears, or repository ownership differs: reject.
- A partial download leaves a cache entry: use staging and atomic rename; revalidate cached content.
- Metadata or artwork has no permission evidence: public export excludes it and reports why.
- Aliases point to multiple identities or relationship targets are absent: reject normalized contract releases.
- A failed update changes the active dataset: resolution only prepares immutable cache entries; activation is separate.
- Raw evidence, service accounts, reports, and runtime state leak into repositories: allowlist source files from runtime imports and the TCG shard manifest only.
- All catalog files load at once: inspect/hash files sequentially and cap artifact extraction bytes.

The repeatable E2E creates local release artifacts, resolves them, corrupts bytes,
tries hostile archives and invalid locks, and writes a JSON receipt. Production
activation remains gated on API equivalence and a disposable rollback proof.
