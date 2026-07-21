# Litigant Portal Docs

The repo's mini wiki: reference material you reach for when you need it.
Day-to-day working guidance lives in [CLAUDE.md](../CLAUDE.md); setup and
deployment basics live in the root [README](../README.md). The repo itself is
the source of truth — when a doc and the code disagree, trust the code and fix
the doc.

## Architecture & design

| Doc                                                      | Purpose                                                             |
| -------------------------------------------------------- | ------------------------------------------------------------------- |
| [ARCHITECTURE.md](./ARCHITECTURE.md)                     | Vision, open contracts, tech stack, patterns, Docker, AI chat shape |
| [REQUIREMENTS.md](./REQUIREMENTS.md)                     | Product requirements and UX principles                              |
| [wcag-strategy.md](./wcag-strategy.md)                   | WCAG 2.2 AA compliance strategy                                     |
| [COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md)           | Component/style-guide approach, a11y and viewport testing           |
| [briefcase-architecture.md](./briefcase-architecture.md) | Three-pocket session state model (design, #177)                     |

## AI chat & agents

| Doc                                            | Purpose                                                          |
| ---------------------------------------------- | ---------------------------------------------------------------- |
| [AGENT_DEV_GUIDE.md](./AGENT_DEV_GUIDE.md)     | Build agents on the chat engine: state, prompts, tools, surfaces |
| [ATTACHMENT_SYSTEM.md](./ATTACHMENT_SYSTEM.md) | How uploads flow into the LLM: inline vs. reader subagent        |
| [ai-tone-guide.md](./ai-tone-guide.md)         | Tone and philosophy for AI-generated user-facing output          |
| [prompts-as-infra.md](./prompts-as-infra.md)   | The prompt layer as LP's core system contract                    |

## Topic Flow & document assembly

| Doc                                                              | Purpose                                            |
| ---------------------------------------------------------------- | -------------------------------------------------- |
| [topic-flow-engine.md](./topic-flow-engine.md)                   | Topic Flow engine: build summary and patterns      |
| [overview-mapped-legal-flow.md](./overview-mapped-legal-flow.md) | Generic 9-stage legal flow (legal review artifact) |
| [docassemble-authoring.md](./docassemble-authoring.md)           | Interview authoring gotchas and patterns           |
| [docassemble-local-dev.md](./docassemble-local-dev.md)           | Local docassemble bench for authoring/testing      |
| [docassemble-qa-hosting.md](./docassemble-qa-hosting.md)         | Hosting docassemble on the QA box (path routing)   |

## Product, demo & research

| Doc                                            | Purpose                                                    |
| ---------------------------------------------- | ---------------------------------------------------------- |
| [user-flows.md](./user-flows.md)               | 3×2 flow matrix (Full AI / Hybrid / Basic × Anon / Auth)   |
| [happy-path-jane.md](./happy-path-jane.md)     | Jane's end-to-end eviction narrative (base for variations) |
| [demo-flow-jane.md](./demo-flow-jane.md)       | Jane's abbreviated 8-step demo flow                        |
| [happy-path-sandra.md](./happy-path-sandra.md) | Sandra's ND name-change narrative                          |
| [demo-strategy.md](./demo-strategy.md)         | Showing the full flow before AI tools/corpus are ready     |
| [expert-feedback/](./expert-feedback/)         | Domain-expert review notes on flows and content            |

## Operations

| Doc                                    | Purpose                                             |
| -------------------------------------- | --------------------------------------------------- |
| [QA-DEPLOY.md](./QA-DEPLOY.md)         | One-time setup for the QA/staging server            |
| [updating.md](./updating.md)           | Updating a hosted LP box (self-hosters, partner IT) |
| [pinned-assets.md](./pinned-assets.md) | Pinned frontend asset versions + update commands    |
| [translation.md](./translation.md)     | i18n workflow (`.po` files, translation markers)    |
| [SECURITY.md](./SECURITY.md)           | Vulnerability disclosure, CSP, production headers   |

## Process & planning records

| Doc                                                                | Purpose                                                   |
| ------------------------------------------------------------------ | --------------------------------------------------------- |
| [issue-conventions.md](./issue-conventions.md)                     | Issue templates, labels, and the reasoning behind them    |
| [sizing-guide.md](./sizing-guide.md)                               | How to size issues (contributor onboarding)               |
| [sizing-calibration.md](./sizing-calibration.md)                   | Living record of sizing calibration passes                |
| [sprint-map.md](./sprint-map.md)                                   | Web-team sprint letters/artists ↔ LP iterations crosswalk |
| [itc-demo-retro.md](./itc-demo-retro.md)                           | Lessons from the ITC demo (Jan 2026)                      |
| [nd-name-change-planning-log.md](./nd-name-change-planning-log.md) | Decision log from ND name-change demo planning            |
