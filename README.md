# Tech Cheat Sheets And Notes

[![Lint](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/actions/workflows/release.yml/badge.svg?branch=main&event=push)](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/actions/workflows/release.yml)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/paypalme/DewaldOosthuizen1)

A growing collection of technology cheat sheets — quick-reference study notes organised by topic
and certification track. Comparisons between services, decision flows, and Mermaid diagrams that
answer "which one and why?" — not step-by-step tutorials or portal walkthroughs.

## Current Content

| Topic |
| ---- |
| [Microsoft Azure](docs/azure/index.md) |
| [Amazon Web Services](docs/aws/index.md) |
| [Google Cloud](docs/google/index.md) |
| [Programming (Java)](docs/programming/java/index.md) |

More topics (other cloud providers, DevOps tooling, architecture patterns) will be added over time.
Each new topic lives under its own subdirectory inside `docs/`.

## Repository Structure

```
docs/
  azure/
    index.md                     — Azure overview (domain index)
    files/
      <domain>/<domain>.md       — One page per domain (networking, security, …)
    diagrams/<section>/         — standalone Mermaid diagram sources (one per file)
      <slug>.mmd                — exam-agnostic slug
  aws/
    index.md                     — AWS overview (domain index)
    files/
      <domain>/<domain>.md       — One page per domain (compute, networking, …)
    diagrams/<section>/
      <slug>.mmd
  google/
    index.md                     — Google Cloud overview (domain index)
    files/
      <domain>/<domain>.md       — One page per domain (compute, networking, …)
    diagrams/<section>/
      <slug>.mmd
  programming/
    java/
      index.md                   — Java overview (topic index)
      files/
        <domain>/<domain>.md     — One page per topic
  index.md                      — MkDocs site home page
mkdocs.yml                      — MkDocs Material site configuration
```

## Local Setup

Requirements: Python 3.11+, Node/npm on PATH.

```bash
# One-time per clone: creates .venv, installs Python + Node deps
make install

# Install pre-commit hooks (optional but recommended)
.venv/bin/pip install pre-commit
.venv/bin/pre-commit install
```

## Viewing the Documentation Site

Serve it locally with hot-reload:

```bash
make start   # opens http://127.0.0.1:8000
```

Build a static copy:

```bash
make docs-build   # output in site/
```

GitHub also renders Mermaid natively in Markdown files. VS Code users can
install `Markdown Preview Mermaid Support` to render diagrams in the editor
preview.

## Running CI Locally

```bash
make ci
```

Runs in order: markdownlint, Mermaid validation, ruff lint + format check,
pytest with coverage, and a strict MkDocs build. A failing `make ci` means
the GitHub Actions pipeline will also fail — fix it before opening a PR.

For dead-link checking, run:

```bash
make link-check
```

`make link-check` bootstraps a pinned Lychee binary into `.tools/` on first
use, so no global Lychee installation is required.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
the full workflow: picking up an issue, branch naming, content style, coding
standards, and the pull request process.

## License

This project is licensed under the [`GPL-3.0`](LICENSE).
