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

## Generated workspace hydration and runner mirror

- A lock omits a registered vertical or introduces an unknown one: reject before copying.
- A verified file changes during copying: hash its staged destination before replacement.
- A source path or destination directory is a symlink: reject; never follow it into another tree.
- Hydration is interrupted: the build gate rejects the mixed workspace; no deployed release is activated.
- Runner cache is missing, corrupt or out of disk budget: fail the build; keep production running.
- An update evicts artifacts referenced by recent locks: retain current, previous and incoming pins.
- The mirror is writable inside CI or receives an operator's personal token: mount archives read-only and transfer files over the existing SSH channel; store no GitHub token in CI.
- A collector output changes during export to its owning repository: reject the snapshot and leave its source manifest uncommitted; never publish automatically.
- A future API import reintroduces a tracked application copy of source JSON: reject workspace ownership verification until that input is generated from its data repository.
