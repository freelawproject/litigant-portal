# Issue Conventions

How issues are filed, categorized, and labeled in litigant-portal. Captures the deliberate choices behind the issue templates and label color scheme so they survive someone "fixing" them later.

## Templates

Four issue-form templates in `.github/ISSUE_TEMPLATE/`. Each auto-applies a single matching label (1-to-1) on creation.

| Template          | Auto-label    | For                                               |
| ----------------- | ------------- | ------------------------------------------------- |
| `bug-report.yml`  | `bug`         | Something broken                                  |
| `enhancement.yml` | `enhancement` | Improvement or change                             |
| `task.yml`        | `task`        | Chore, refactor, docs, infra, tech debt           |
| `qa-round.yml`    | `qa`          | QA round — request and findings live in one issue |

**Filers layer additional labels** (e.g., `tech debt`, `frontend`, `a11y`) at creation or triage.

**Priority and size are not in the templates.** The team assigns those during sprint grooming — outsiders don't pick them.

**No title prefixes** (`fix:`, `feat:`, etc.). The auto-applied label carries the type signal.

**Blank issues are disabled** in `.github/ISSUE_TEMPLATE/config.yml` to force template use.

**Security vulnerabilities** route through `SECURITY.md` at the repo root, which points to FLP's VDP (`https://free.law/vulnerability-disclosure-policy/`). The GitHub "Report a security vulnerability" chooser entry picks up `SECURITY.md` automatically.

## Label color scheme

Labels are visually grouped by category. Colors are chosen deliberately — don't change them without updating this doc.

### Core / template auto-applied

| Label         | Color     |
| ------------- | --------- |
| `bug`         | `#d73a4a` |
| `enhancement` | `#a2eeef` |
| `task`        | `#0e8a16` |
| `qa`          | `#ba2e0d` |

### Priority — heat map (hot → cool with urgency)

| Label | Color     | Meaning                      |
| ----- | --------- | ---------------------------- |
| `P0`  | `#B60205` | Critical — fire              |
| `P1`  | `#D93F0B` | High — sprint commitment     |
| `P2`  | `#FBCA04` | Medium — sprint stretch      |
| `P3`  | `#C5DEF5` | Low — known work, not urgent |

### Size — uniform soft grey (intentionally muted)

All `size:` labels share `#cfd3d7`. Sizing is metadata, not urgency. Uniform grey keeps size labels visually quiet so priority and area colors dominate the eye.

| Label      | Color     |
| ---------- | --------- |
| `size: XS` | `#cfd3d7` |
| `size: S`  | `#cfd3d7` |
| `size: M`  | `#cfd3d7` |
| `size: L`  | `#cfd3d7` |
| `size: XL` | `#cfd3d7` |

### Component / area

Each surface area gets its own distinct hue so multi-label issues are scannable.

| Label           | Color     | Notes                                          |
| --------------- | --------- | ---------------------------------------------- |
| `ai`            | `#7B61FF` | AI, LLM, agents, prompts, RAG                  |
| `backend`       | `#D4A017` | Django views, services, models, business logic |
| `frontend`      | `#aaaaaa` | Templates, CSS, JS, Alpine.js — the UI layer   |
| `infra`         | `#333333` | DevOps, hosting, CI/CD, environment            |
| `documentation` | `#0075ca` | Docs additions or improvements                 |
| `security`      | `#9333EA` | CSP, auth, PII, data retention, trust          |
| `a11y`          | `#EC4899` | Accessibility — mission-aligned user impact    |

### Workflow / state

| Label              | Color     | Notes                                                        |
| ------------------ | --------- | ------------------------------------------------------------ |
| `duplicate`        | `#cfd3d7` | GH default — triage convenience                              |
| `good first issue` | `#7057ff` | GH default                                                   |
| `help wanted`      | `#008672` | GH default                                                   |
| `pinned`           | `#006b75` | Exempt from stale bot                                        |
| `question`         | `#d876e3` | GH default — further information requested                   |
| `research`         | `#06B6D4` | Investigation / learning, not code                           |
| `stale`            | `#ededed` | No activity for 90+ days                                     |
| `tech debt`        | `#D4C5F9` | Deferred cleanup, consolidation, refactoring                 |
| `user story`       | `#0FB3A1` | Persona user story — living reference, exempt from stale bot |

## Conventions

- **Lowercase, spaces (no hyphens)** for multi-word labels. Matches GitHub defaults (`good first issue`, `help wanted`).
- **1-to-1 template ↔ label mapping** for the four core templates.
- **No color duplicates.** Every label has a unique hex so visual scanning isn't ambiguous.
- **Color category** (heat map / muted / hue) signals the kind of metadata at a glance, not just the specific value.

## When updating

- Don't change a label color without updating this doc.
- Don't add a color that duplicates an existing one — audit first.
- Adding a new template? Add a 1-to-1 label and document it here.
- Removing a label? Note any in-flight issues using it; deleting strips the label silently.

## History

- 2026-05-20 — initial issue templates set up (bug-report, feature, task) + chooser config + qa-round URL fix. PRs #433 (qa) and #435 (main).
- 2026-05-21 — templates tightened per QA feedback: `feature` renamed to `enhancement`; priority and size dropdowns removed from all templates; title prefixes dropped; `qa-round` converted from markdown to issue form; root `SECURITY.md` added for VDP routing. PR #436 (qa) + direct cherry-pick to main.
- 2026-05-21 — label audit: 32 → 28 labels. Resolved color collisions (`security`, `research`, `a11y`); sizes unified to soft grey; deleted unused `blocked`, `invalid`, `wontfix`, `Chat Flow`. Created `task` label; renamed `QA` → `qa` (lowercase).
- 2026-06-15 — added `user story` label (`#0FB3A1`) and added it to the stale bot's exempt list, so persona stories under #22 don't auto-close. Applied to #26, #190, #191, #192, #311, #312.
- 2026-06-16 — dropped the dead `blocked` reference from `stale.yml` (label was deleted in the 2026-05-21 audit); renamed the new label `user-story` → `user story` to match the no-hyphens convention.
