# Contributing

Submit a pull request to the relevant `metadata-fyi/data-<vertical>` repository.
Collectors must not push to main. Preserve stable IDs and document corrections,
source URLs, source snapshot hashes and collection dates. Changes to aliases or
relationships must include target identities and checks for ambiguity/dangling links.

Public exports require reviewed per-record metadata permission evidence. Media
requires creator, license identifier and URL, attribution, permission reference,
source URL, acquisition date, SHA-256, dimensions and any derivative transforms.
Original contributor photos must include an explicit permission declaration.
Unknown permission means exclude the record/file from public export and report
it in coverage counts. A code license never supplies image permission.

Never include credentials, runtime or customer data, local review archives,
private agreements or contact details. Public pull-request CI runs without
production credentials. Trusted release workflows require maintainer review.
