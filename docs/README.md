# Litigant Portal Docs

The repo's reference shelf: material you reach for when you need it. Day-to-day working guidance lives in [CLAUDE.md](../CLAUDE.md); setup, deployment, and contributing basics live in the root [README](../README.md) and [CONTRIBUTING.md](../CONTRIBUTING.md). The repo itself is the source of truth — when a doc and the code disagree, trust the code and fix the doc.

`wiki/` is deliberately in-repo rather than a hosted wiki: docs version with the code you pulled. Fork the repo, or stay on an older release, and the docs describe _that_ version.

## AI tooling

| Doc                                                   | Purpose                                                          |
| ----------------------------------------------------- | ---------------------------------------------------------------- |
| [AGENT_DEV_GUIDE.md](./ai-tooling/AGENT_DEV_GUIDE.md) | Build agents on the chat engine: state, prompts, tools, surfaces |
| [UPLOAD_SYSTEM.md](./ai-tooling/UPLOAD_SYSTEM.md)     | How uploads flow into the LLM: inline vs. reader subagent        |

## Document assembly

| Doc                                | Purpose                                                 |
| ---------------------------------- | ------------------------------------------------------- |
| [docassemble.md](./docassemble.md) | docassemble: authoring gotchas, local bench, QA hosting |

## Wiki

| Doc                                                 | Purpose                                                                                                           |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| [SECURITY.md](./wiki/SECURITY.md)                   | Security architecture: production headers, secrets, CSP                                                           |
| [ai-tone-guide.md](./wiki/ai-tone-guide.md)         | Tone and philosophy for AI-generated user-facing output                                                           |
| [issue-conventions.md](./wiki/issue-conventions.md) | Issue templates, labels, and the reasoning behind them                                                            |
| [translation.md](./wiki/translation.md)             | gettext infrastructure reference (strategy: [#704](https://github.com/freelawproject/litigant-portal/issues/704)) |
| [wcag-strategy.md](./wiki/wcag-strategy.md)         | WCAG 2.2 AA compliance strategy + component checklist                                                             |
