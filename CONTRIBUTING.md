# Contributing Guidelines

Thanks for your interest in contributing! 🎉  
We welcome all contributions - code, documentation, bug reports, or ideas.

When contributing, remember to follow our [Code of Conduct](https://github.com/4TUResearchData/djehuty/blob/main/CODE_OF_CONDUCT.md).

## How to Contribute?
- **Report bugs or request features** by opening an issue.
    - By opening an issue you can be in touch with us to request a new feature or report a bug. Check in the Report bugs or request features section how to make the request.
- **Code contributions:** pick an open issue or propose a new idea.
    - Do you have development skills? You also can contribute by helping us to develop Djehuty. Check the Code contributions section on how to become a developer contributor.

## Recognition of Contributions

All contributions - whether it’s code, bug reports, or ideas are appreciated and recognized. Contributors may be credited in release notes or project acknowledgments. Thank you for helping make the project better!

## Contribution workflows

### Report bugs or request features

We welcome contributions in the form of bug reports and feature suggestions. Here’s how to make them most useful:

1. **Look for Existing Issues**

    Before opening a new report or suggestion, [check the issue tracker](https://github.com/4TUResearchData/djehuty/issues) to see if it’s already been raised. This helps prevent duplicates and keeps the conversation focused.

2. **Submit a New Issue**

    If you don’t find an existing issue, create a new one [using the appropriate template](#issue-template). Add relevant labels if applicable.

3. **Provide Useful Information**

    - **For Bugs:** Explain the steps to reproduce the problem, what you expected to happen, what actually happened, and include any relevant screenshots, logs, or environment details.
    - **For Feature Suggestions:** Describe the idea clearly and explain why it would improve the project.

4. **Participate in Discussion**

    Be ready to answer questions or provide additional details. Open discussion helps the team understand the issue and work toward the best solution.

### Code contributions

1. **Contact us!**

    Before starting any work, please **contact repository maintainers at [info@djehuty.4tu.nl](mailto:info@djehuty.4tu.nl)** to discuss how your idea fits with our strategic goals.

2. **Check or open an issue**

    Before you start work, **search the [issue tracker](https://github.com/4TUResearchData/djehuty/issues)** to see if your idea is already being discussed.

    - If you find a relevant issue, comment to say you’re taking it on and, if possible, assign yourself. If you cannot assign, leave a comment like “Working on this” so maintainers know.
    - If no issue exists, open a new issue using the [issue template](#issue-template) and include: a short, descriptive title; a brief explanation of the problem or feature and why it’s needed.
      - ⚠️ **IMPORTANT**: **Do not discuss security-related aspects**: to report a vulnerability, please see [SECURITY.md](https://github.com/4TUResearchData/djehuty/blob/main/SECURITY.md)

3. **Work from a fork**

    Contributors should work from a fork of the repository. Maintainers may work directly on the main djehuty instance. If you’re new to the fork-and-pull-request workflow, [check out the First Contributions](https://github.com/firstcontributions/first-contributions) guide for a step-by-step introduction.

4. **Clone and create a branch**

    Clone your fork to your local machine and create a new branch for your work.

5. **Set up your development environment**

    Follow the [Development environment](#development-environment) instructions below to install the prerequisites, start a local instance, and run the tests. Make sure you can build and test the project locally before starting your contribution.

6. **Work on your branch and open a PR**

    - Make your changes on your branch.
    - Commits must be verified, see the [commit signature verification guide](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification) for more details.
    - Once your work is ready for review, open a Pull Request (PR) against the main project repository.
      - Provide a clear description of what you changed and link the related issue.
      - Use the [PR template](#pull-request-template) and check the approval checklist before submitting.
      - ⚠️ **IMPORTANT**: **Do not open a PR for a security issue**: to report a vulnerability, please see [SECURITY.md](https://github.com/4TUResearchData/djehuty/blob/main/SECURITY.md)

7. **Final approval and merge**

    After review and approval, your PR must be squashed into a single commit using the project’s [commit message template](#commit-message-template). Once the checklist is complete, a maintainer will rebase-merge it into the main branch to keep the history clean.

If you want to make a very small contribution, such as one or a few lines of code for which following the code contributions workflow is not convenient, please contact the [core maintainers](mailto:info@djehuty.4tu.nl).

---

## Development environment

### Prerequisites

- [Git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker](https://docs.docker.com/get-docker/) (with Compose)
- [just](https://github.com/casey/just#installation)

### Getting started

```bash
git clone https://github.com/4TUResearchData/djehuty.git
cd djehuty/
```

To install your working copy into the current Python environment:

```bash
pip install .
```

### Running the development environment

To spin up a fully working local instance, run:

```bash
just dev
```

This builds and starts Docker containers for djehuty and
[Virtuoso](https://github.com/openlink/virtuoso-opensource) (SPARQL store).
On first run, the database is automatically initialized with categories,
licences, and a dev account with full admin privileges — no extra setup needed.

Once running:

- **Djehuty**: http://localhost:8080 (auto-login, no auth setup needed)
- **Virtuoso SPARQL**: http://localhost:8890/sparql (useful for troubleshooting)

Edit any Python file under `src/` and the server reloads automatically.

To start the development environment with a Virtuoso database backup
(e.g. to test against specific production data):

```bash
just db_backup=path/to/prod-2025-10-09_#1.bp dev
```

Point `db_backup` at any one of the backup files. All siblings sharing
the same prefix in that directory are applied in order, so a full backup
plus its incrementals (e.g. `prod-2025-10-09_#1.bp`, `…_#2.bp`,
`…_#3.bp`) are restored together.

To stop and remove the development environment, run `just clean`.
To see all available commands, run `just --list`.

### Running the tests

The project includes an end-to-end test suite built with
[Playwright](https://playwright.dev/python/) and
[pytest](https://docs.pytest.org/). Tests run against a live djehuty +
Virtuoso stack seeded with test data — all in containers, so no host
Python or browser setup is required.

```bash
just test
```

That single command builds the test image (with Playwright and
chromium), brings up Virtuoso and djehuty, loads the SPARQL
permissions, runs `--initialize`, applies the seed dataset, and runs
the suite inside the docker network. Coverage data lands in
`docker/coverage/`; failure screenshots in `docker/test-results/`.

Filter the run with any pytest argument:

```bash
just test -m smoke              # one marker
just test -k test_homepage      # by keyword
just test tests/test_auth.py    # specific file
```

#### Marker isolation

CI runs each marker (`smoke`, `auth`, `dataset`, `admin`, `embargo`,
`citation`, `versioning`, …) in its own job with a fresh stack, so a
test never sees data left over from another marker. `just test` runs
everything against one shared stack, which is faster but means a few
state-sensitive tests can fail locally that pass in CI. When that
happens, run the affected marker on its own:

```bash
just clean   # drop volumes for a truly fresh stack
just test -m citation
```

#### CI

Tests run automatically on every push via GitHub Actions. Each runner
in the matrix invokes `just test -m <marker>` against the same compose
stack used locally, so a green `just test` on your laptop reproduces
what CI sees. Screenshots are captured on failure and uploaded as
artifacts; coverage from each shard is combined into a single report.

### Linting

Code style is enforced with [Ruff](https://docs.astral.sh/ruff/) and
rolled out incrementally: only paths that have already been cleaned are
checked (in the `include` list under `[tool.ruff]` in `pyproject.toml`),
starting with `src/djehuty/utils/`.

```bash
just lint
```

This runs `ruff check` (bugs, style errors, import sorting) and
`ruff format --check` over the cleaned paths, using the Ruff version pinned
in `uv.lock`. CI runs the same recipe on every push and pull request, so a
clean `just lint` locally means a green Lint job.

```bash
just format
```

That applies Ruff's automatic formatting and fixes to the same paths.

### Building the documentation

The documentation site is built with MkDocs. See
[Documentation](https://github.com/4TUResearchData/djehuty/blob/main/README.md#documentation)
in the README for how to build and preview it locally.

---

## Conventions


### Code conventions

Follow existing code conventions and existing patterns such as:

- **Naming conventions**: Follow existing patterns for variables, functions, classes, and file names.
    - Use snake_case for functions and variables.
    - Be descriptive but concise in names.
- **Indentation**: Use the same indentation style (tabs vs. spaces, number of spaces) already present in the codebase.
    - Line length: Keep lines within the project’s limit (100 characters, enforced by Ruff).
    - Comments & docs: Write comments/docstrings in the same style.
- **No unused code**: Remove dead or commented-out code before committing.
- **Linting**: Run `just lint` before committing (or format using `just format`).


### Commits

All **commits will be squashed into a single commit** before merging into main. This has two purposes:

- **Clean history**: The main branch stays tidy.
- **Readable log**: Each merge commit clearly tells the story of a completed change.

When planning a change remember to:

- **Limit the scope**: Keep the diff as small as possible so reviewers can understand the change quickly.
- **Avoid commit noise**: Don’t include generated files, formatting-only changes, or experimental code unless they are the sole purpose of the commit.

For the **squashed commit message** please also have a look at the [commit message template](#commit-message-template).


### Branch Naming Conventions

Branches must follow a **consistent naming scheme** to make collaboration, reviews, and automation easier.
Use the following pattern:

```markdown
wip-<type>-<issue-number>-<short-description>
```

```markdown
- wip = prefix for “Work in Progress”
- type = category of change (bug, feat, impr, docs, chore)
- issue-number = the GitHub issue number related to the work (if applicable)
- short-description = a brief, kebab-case summary of the change
```
#### Example of branch name:

| Type  | Branch name example               | When to use                      |
| ----- |-----------------------------------| -------------------------------- |
| bug   | wip-bug-123-fix-login-crash       | Bug fixes                        |
| feat  | wip-feat-007-add-endpoint         | New features                     |
| impr  | wip-impr-321-optimize-query       | Improvements, refactors, cleanup |
| docs  | wip-docs-789-update-install-guide | Documentation updates            |
| chore | wip-chore-101-bump-dependencies   | Maintenance or config updates    |

---

## Releases

Releases are handled by maintainers and automated by GitHub Actions. See [RELEASE.md](https://github.com/4TUResearchData/djehuty/blob/main/RELEASE.md) for the step-by-step procedure.

---

## Templates

### Issue Template

#### 🐞 Bug
Use when something is **broken** or misbehaving (broken functionality).

```markdown
**Describe the bug**
A clear and short description of the bug.

** Steps to Reproduce**
Steps to reproduce the behavior:

1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and short description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain the problem.

**Your personal set up:**
 - Smartphone or Desktop
 - OS: [e.g. iOS]
 - Browser [e.g. chrome, safari]

**Additional context**
Add any other context about the problem here.
```


#### 🪴 **Improvement**
Use when you want to refine an **existing functionality** (enhance functionality).

```markdown
**Summary**
A clear and short description of the enhancement.

**Current Behavior**
Brief description of the existing behavior or limitation.

**Proposed Improvement**
How you suggest to improve it.

**Additional Notes**
References, related issues, examples.
```

#### 🚀 **New Feature**
Use when you would like to introduce a **new idea**.

```markdown
**Summary**
A short description the functionality and who will use it.

**Is your feature request related to a problem? **
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear and concise description of what you want to happen. 

Suggestion: if possible, describe who will benefit from the functionality and for what reason.
Example:
- As a "data steward", I want "to do ..." so that "i can ....".
- As a "researcher", I want "to do ..." so that "i can ....".
- As a "reviewer", I want "to do ..." so that "i can ....".

**Additional Context**
Designs, diagrams, examples, screenshots etc.
```
---
### Pull Request Template
Regardless of the issue type, **use the PR template below**. Note that some PRs may not be associated with an issue.

```markdown
**Summary**
A clear and short description of the change. Please provide what and why.

**Changes**
- filename: description of key update. Keep it concise.

**Approval Checklist**
- [ ] I agree to follow _Djehuty's_ [code of conduct](https://github.com/4TUResearchData/djehuty?tab=coc-ov-file#readme).
- [ ] I have read and I have follow the [code contribution workflow](https://github.com/4TUResearchData/djehuty/blob/main/CONTRIBUTING.md).
- [ ] Code style and conventions were respected.
- [ ] Documentation has been updated where needed (README, docs, or examples).
- [ ] Review approved by at least one maintainer.
- [ ] Merge readiness (PR is squashed into a single commit and follows the [commit template](https://github.com/4TUResearchData/djehuty/blob/main/CONTRIBUTING.md#commit-message-template)).

**Issue Reference (optional - PRs may not be associated with an issue)**
Closes #ISSUE_NUMBER

**Screenshots (optional)**
Before/After visuals, UI changes, or relevant logs.

**Notes (optional)**
Additional context, caveats, or follow-up tasks.
```
---

### Commit Message Template

The **commits in djehuty have a specific format**. By being detailed in your commit message, you help specific changes to the software be more traceable, and if necessary, revertible.

The commits should be clear and focused. In the commit message:

- The first line provides a general idea of what change has been done and in which part of code.
- The following lines give a one-line summary of changes made to each individual file with the commit.
- If a line extends 80 characters, a line break should be introduced.
- Imperative mood (e.g. “Add test for …”, “Implement error handling …”, “Fix UUID validator …”) is used to describe the changes made.

The message follows the format:
```markdown
[folder]:[subfolder]: <Describe a change in one line>
* [path to 1st file changed]: <Describe change in the file>
* [path to 2nd file changed]: <Describe change in the file>
* [path to 3rd file changed]: <Describe change in the file>
```
...

Example of a commit message:
```markdown
web: html_templates: Add keyword autocomplete options.
* src/djehuty/web/resources/html_templates/depositor/edit-dataset.html: Add
  ID for displaying keyword autocomplete and edit help text.
* src/djehuty/web/resources/static/js/edit-dataset.js: Load keyword
  autocomplete options when typing a keyword.
* src/djehuty/web/resources/html_templates/depositor/edit-collection.html: Add
  ID for displaying keyword autocomplete and edit help text.
* src/djehuty/web/resources/static/js/edit-collection.js: Load keyword
  autocomplete options when typing a keyword.
* src/djehuty/web/resources/static/js/utils.js: Add method to search keyword
  options and load them as an autocomplete dropdown.
```

---

## Label Guide

To help indicate the status of issue or pull request discussions, maintainers will [apply labels](https://github.com/4TUResearchData/djehuty/labels) to each as described below:

| Label | When to use |
|-------|-------------|
| 🐞 ![bug](https://img.shields.io/badge/bug-red?style=flat) | Something is broken or behaves unexpectedly|
| 🪴 ![improvement](https://img.shields.io/badge/improvement-d4c5f9?style=flat) | Refining current functionality |
| 🚀 ![new feature](https://img.shields.io/badge/new_feature-mediumseagreen?style=flat) | Introducing functionality that did not previously exist  |
| 📚 ![documentation](https://img.shields.io/badge/documentation-0075ca?style=flat) | Docs updates, corrections, or additions |
| 🔧 ![refactor](https://img.shields.io/badge/refactor-c2e0c6?style=flat) | Internal code restructuring without changing external behavior |
| 🌱 ![good first issue](https://img.shields.io/badge/good_first_issue-ABE6E4?style=flat) | Beginner-friendly tasks with clear steps |
| 💬 ![needs discussion](https://img.shields.io/badge/needs_discussion-moccasin?style=flat) | Further clarification or consensus is required |
| ⛔ ![blocked](https://img.shields.io/badge/blocked-indianred?style=flat) | Waiting on dependencies, or prerequisites |
| ![wontfix](https://img.shields.io/badge/wontfix-FFF?style=flat) | This will not be worked on
| ![duplicate](https://img.shields.io/badge/duplicate-lightgray?style=flat) | Waiting on dependencies, or prerequisites |

---

💡 By contributing to this project, you help us build a positive and supportive community. Thank you!
