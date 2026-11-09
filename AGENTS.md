# AGENTS.md

djehuty is a research data repository system developed by
4TU.ResearchData. Researchers use it to deposit, publish and cite
datasets and other research output. State is stored as RDF in a
SPARQL 1.1 store (Virtuoso or Jena Fuseki), not in a relational
database. Instances are configured, not forked: branding, menus,
identity provider and storage back-ends are configuration.

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. This file only adds
what coding agents need; the contribution rules there apply to you too.

## Where things live

- `src/djehuty/api/` and `src/djehuty/application.py`: route
  definitions (the API reference is generated from these)
- `docs/`: Markdown documentation (MkDocs); `docs/contributing.md`
  has a tour of the source code
- `docs/knowledge-graph.md`: the RDF data model
- `docs/running-djehuty.md`: every configuration option
- `community/`: Quarto sources for the community site

## Commands

Use the `just` recipes rather than calling tools directly
(prerequisites: Git, uv, Docker with Compose, just).

- Start a local instance: `just dev` (djehuty on http://localhost:8080,
  reloads when files under `src/` change)
- Stop and remove it: `just clean`
- Run tests: `just test` (filter with `-m <marker>`, `-k <keyword>`
  or a file path)
- Lint and format: `just lint`, `just format`
- Preview the docs: `just docs-md-serve` (Markdown pages only). After
  changing an endpoint, re-run `just openapi`; after changing
  `community/`, re-run `just docs-community`.
- List all commands: `just --list`

Run `just lint` and `just test` before proposing a change.

## Things to know

- - Ruff settings, including which paths it checks, are in
  `[tool.ruff]` in `pyproject.toml`. Do not reformat files outside
  those paths. Python version and dependencies are defined there too.
- Tests are end-to-end (Playwright and pytest) and run in containers
  against a live djehuty and Virtuoso stack.
- CI runs each marker on a fresh stack. If a test fails in a full local
  run, run that marker alone after `just clean`.
- The published documentation site (Markdown docs, API reference and
  community site) is built in CI. Never edit or commit generated
  output; change the sources instead.

## Conventions

- Keep changes focused; avoid unrelated modifications.
- Use Conventional Commits (`feat:`, `fix:`, `docs:`) when possible.
- Commits must be verified, so they need the contributor's own
  signing setup. Pull requests are squashed before merging.
- Do not change license or copyright headers.
- Never put secrets or credentials in the repository.

## Security

Never discuss security issues in public issues or pull requests, and
never open a pull request for one. See [SECURITY.md](SECURITY.md).

## GitHub interaction

- Never open issues or pull requests unless a person explicitly asks.
- Never post comments, progress updates or review replies on GitHub on
  someone's behalf unless asked. If you do, say it was written by an
  AI tool on behalf of that person.

## AI-assisted work

The project's policy is in the "Use of AI tools" section of
[CONTRIBUTING.md](CONTRIBUTING.md#use-of-ai-tools). In short:

- A person is responsible for every change and must review and
  understand it. Explain your changes to them clearly.
- Do not add AI co-author trailers to commits.
- If you found a possible bug, try to reproduce it before reporting it,
  and say what you could not verify or test.