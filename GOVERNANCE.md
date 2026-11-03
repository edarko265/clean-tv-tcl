# Governance

Clean TV TCL is maintained by the repository owner, [@edarko265](https://github.com/edarko265).

## Decision making

Routine changes are discussed in issues and reviewed through pull requests. The maintainer weighs device safety, restore behavior, privacy, performance on low-resource televisions, accessibility, licensing, and long-term maintenance.

The maintainer has final responsibility for scope, releases, security response, and project policy. Significant changes should record their rationale in an issue or architecture document before implementation.

## Branches and releases

- `main` contains stable, release-ready work.
- `dev` is the integration branch.
- Feature and fix branches target `dev`.
- A merge into `main` requires explicit approval from the repository owner after CI, review, and real-device verification appropriate to the change.
- Direct pushes to `main` are not part of the normal workflow.
- Releases use semantic versioning where practical and include rollback notes for device-facing changes.

Repository settings should require a pull request, passing checks, resolved review conversations, and maintainer approval before `main` can change.

## Upstream relationship

This repository is an independent derivative of [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv). Upstream changes are fetched through the `upstream` remote, reviewed on a dedicated synchronization branch, tested, and merged into `dev`. They are never merged directly into `main`.

Project-specific features may intentionally diverge, but upstream authorship, license notices, and commit history remain intact.

## Community standards

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Technical contributions follow [CONTRIBUTING.md](CONTRIBUTING.md); confidential reports follow [SECURITY.md](SECURITY.md).
