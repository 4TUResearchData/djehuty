# AGENTS.md

djehuty is a research data repository system developed by 4TU.ResearchData. State is stored as RDF in a SPARQL 1.1 store, not in a relational database. Instances are configured, not forked: branding, menus, identity provider and storage back-ends are configuration.

See [README.md](README.md) for an overview and read [CONTRIBUTING.md](CONTRIBUTING.md) first for the contribution rules, which apply to you too. This file only adds what coding agents need.

## Where things live

- `src/`: source code
- `tests/`: tests 
- `docs/`: documentation (the published site is built in CI; never commit generated output) The knowledge graph documentation is known to be incomplete and may not reflect the current implementation.

## Commands

Use the `just` recipes rather than calling tools directly (prerequisites: Git, uv, Docker with Compose, just). Run `just --list` to see what is available and `just --show <recipe>` to see what a recipe does.

- Before proposing a change, run `just lint` and `just test-unit`.
- Run unit tests: `just test-unit` (fast, no containers; filter with `-k <keyword>`).
- Run end-to-end tests: `just test` (filter with `-m <marker>` or `-k <keyword>`; a file path does not filter, the whole suite runs). Use it when behaviour changes.
- Ruff only checks the paths listed in `pyproject.toml`. Do not reformat files outside them.

## Rules

- Do not change license or copyright headers.
- Never discuss security issues in public issues or pull requests, and never open a pull request for one. See [SECURITY.md](SECURITY.md).
- Never open issues or pull requests unless a person explicitly asks.
- Never post comments or review replies on GitHub on someone's behalf unless asked. If you do, say it was written by an AI tool on behalf of that person.

## AI-assisted work

The project's policy is in the "Use of AI tools" section of [CONTRIBUTING.md](CONTRIBUTING.md#use-of-ai-tools). In short:

- A person is responsible for every change and must review and understand it.
- Do not add AI co-author trailers to commits.
- Try to reproduce a possible bug before reporting it, and say what you could not verify.