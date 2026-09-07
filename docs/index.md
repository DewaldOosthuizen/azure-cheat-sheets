# Tech Cheat Sheets And Notes

[![Lint](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/actions/workflows/release.yml/badge.svg?branch=main&event=push)](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/actions/workflows/release.yml)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/paypalme/DewaldOosthuizen1)

Quick-reference study notes for technology certifications and architecture decisions.
Each sheet answers *which service, which pattern, and why* — not how to click through a portal.
Content is comparison-oriented: tables, decision flowcharts, and Mermaid diagrams side-by-side.

---

## Cloud Service Providers

| Provider | Domain Index |
|----------|--------------|
| [Microsoft Azure](azure/index.md) | organised by domain |
| [Amazon Web Services](aws/index.md) | organised by domain |
| [Google Cloud](google/index.md) | organised by domain |

See the [Azure Exam Track Index](azure/index.md), [AWS Exam Track Index](aws/index.md) and [Google Cloud Exam Track Index](google/index.md) for full certification coverage.

---

## Programming

| Topic | Index |
|-------|-------|
| [Java](programming/java/index.md) | language fundamentals, Spring Boot, persistence |

---

## How to Use These Sheets

The cheat sheets are not meant to be read cover-to-cover. Jump to the section relevant to what
you are studying. Each section contains:

- A comparison table of services in that domain
- Exam-tip callouts that highlight common decision points in exam questions
- One or more Mermaid decision flowcharts for branching "which service?" scenarios
- Deprecation notices where a service has been retired or superseded

The live site renders all diagrams inline. To browse locally, run `make docs-serve`.

---

## Contributing

See [CONTRIBUTING.md](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/blob/main/CONTRIBUTING.md)
for the full contributor workflow.

## License

This project is licensed under the [`GPL-3.0`](https://github.com/DewaldOosthuizen/tech-cheat-sheets-and-notes/blob/main/LICENSE).
