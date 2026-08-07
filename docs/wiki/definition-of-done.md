# Definition of Done

## Purpose

This "Definition of Done" is an informal, verbal contract among contributors to litigant-portal: the shared bar for what "done" means, independent of the process mechanics covered in [CONTRIBUTING.md](../../CONTRIBUTING.md) (branching, commits, how to open a PR). It captures the team's agreement snapshotted on 2026-07-30. It is a living document: update it as the team's practices evolve, and note the date/PR when you do.

The statements here are our ideal practices. We don't technically enforce all of them, but we strive to follow them under normal circumstances. Keep each other honest and call out deviations so we can evaluate, adapt, and update as needed.

This document is the **canonical bar for every PR and issue**. Ticket-specific acceptance criteria still live on the issue itself (per CONTRIBUTING.md): that's _additional_, scoped criteria on top of this baseline, not a substitute for it.

## What "done" means to us

### Pull requests: in all cases

- Code review is complete and approved with no outstanding issues.
- Commits are meaningful and atomic where practical; obvious "fixup"/"wip" commits are squashed or amended before merge. (We merge via GitHub's standard "Merge pull request" commit, not squash or rebase: atomicity is about commit _content_, not repo-wide linear history.)
- All automated PR checks pass: `lint.yml` (pre-commit: ruff, djlint, prettier, csp-inline-check) and `tests.yml`.
- The PR contains all relevant changes for its issue. Split into multiple PRs only if technically required; adjacent problems noticed along the way get filed as new issues, not folded in.
- Every PR closes its issue with a closing keyword (e.g. "Closes #220").
- No new linter/formatter warnings, no known regressions introduced.

### Issues: in all cases

- All ticket-specific acceptance criteria on the issue are met.
- Known bugs are either fixed or tracked in their own issue, with team acknowledgment that they're deferred.
- **Test our code, not libraries.** Tests fail when our logic breaks, not because they assert static copy or re-verify Django/framework behavior. `make test` is the bar; if coverage feels thin, the team explicitly agrees it's sufficient rather than leaving it unspoken.
- **WCAG 2.2 AA is met, not treated as a target.** See [wcag-strategy.md](wcag-strategy.md). Automated checks (axe/Lighthouse per CI) plus a manual pass (keyboard-only, zoom to 200%, color-only-info check) for anything touching UI.
- **CSP compliance:** no inline event handlers, Alpine.js CSP-build patterns only (dot-paths, no inline expressions), enforced by `csp-inline-check` but worth a manual look for anything hand-rolled.
- **Progressive enhancement holds:** base workflows still work without JavaScript. Our users are on flaky courthouse wifi and old devices, not just modern browsers.
- **Atomic-design check, both directions:** composes existing atoms/molecules/organisms rather than hand-rolled HTML (top-down); any pattern repeated across 3+ templates gets extracted into a new component (bottom-up). Style guide (`style_guide.html`) updated if a component or prop changed.

### Deploy & release safety: in all cases

- **`main` is never knowingly broken.** Every merge to `main` triggers `deploy.yml`, which runs the test suite, then builds and publishes a Docker image to Docker Hub, then rolls it out to `litigantportal.com` on the CL EKS cluster. Nothing is manual after the merge, so we don't merge code we know is broken or incomplete, a failing test stops the pipeline before anything is published.
- **QA is a manual deploy.** `qa.litigantportal.com` ships via `qa-deploy-do.yml`, currently to the DigitalOcean box until the AWS `qa-litigant` env is wired up. It is deliberately not test-gated: it's the lever for putting a work-in-progress branch in front of a stakeholder. There is no `staging` pipeline: prod-on-merge plus manual QA covers our needs (#461).
- **Migrations are safe to run unattended.** The prod container runs `manage migrate` automatically on every deploy, with no manual gate. Migrations must be backward-compatible with the code currently running (additive columns, no dropping/renaming something still read by in-flight code) unless the team has explicitly agreed to a destructive one and planned around it.
- **New dependencies are checked for known vulnerabilities** before merge. No dependency with an open critical/high advisory goes in without a team decision to accept the risk.

### If relevant

- User-facing copy changes follow the content style rules in [CLAUDE.md](../../CLAUDE.md#content-style-user-facing-copy): no em-dashes, one paragraph per line in corpus bodies, never label a resource "official," solve the litigant's question directly and route to legal aid only when genuinely required.
- Security-relevant changes (auth, PII, data retention, CSP) reviewed with that lens explicitly; anything found gets reported per [SECURITY.md](../../SECURITY.md), not fixed silently in an unrelated PR.
- Public-facing docs (README, style guide, help content) updated, or an issue filed to update them later if not urgent.
- Internal docs (this file, CLAUDE.md, docs/wiki/\*) updated when the change alters a documented process or architecture decision.
- During the Beta Demo push specifically: every button/link does something real, no placeholders, and any partner-specific data that isn't available yet is replaced with court-neutral information rather than a stub.

## FAQ

**Who merges a pull request?**
The author merges after CI is green and at least one other contributor has approved. Given the team's size, the author is sometimes the only person who deeply understands the change: approval still requires someone else to actually read the diff, not rubber-stamp it.

**What if CI is red: can I merge anyway?**
No. A red `lint.yml` or `tests.yml` blocks merge. If a check is flaky (not failing on your change), say so in the PR and get another contributor to confirm before overriding.

**Who closes an issue?**
Whoever merges the PR that closes it, via the closing keyword. No separate sign-off step is required for most issues. For issues carrying accessibility or content-style implications, a second contributor should have looked at the acceptance criteria before merge, even informally.

**Do we need a stakeholder or product owner to review before closing?**
Not for most issues. We trust contributor judgment. For court-partner-facing content, or where legal-review concerns are flagged (e.g. #620), get a second read before closing.

**Can I use the QA box for a stakeholder demo?**
Yes (`qa.litigantportal.com`, deployed manually via `qa-deploy-do.yml`), but it's a temporary environment (see `deploy/qa-do/README.md`), not a durable staging ground. It can be redeployed/wiped at any time; don't treat anything on it as persistent, and confirm it's in the right state shortly before a demo rather than assuming it still is.

**What if I disagree with something in this document?**
Raise it with the team: this is a living snapshot, not policy handed down. Update this file and note the date and PR in History below.

## History

- 2026-07-30: initial Definition of Done for litigant-portal, consolidating the quality-bar criteria previously duplicated in CONTRIBUTING.md into this canonical file.
- 2026-07-30: removed em-dashes throughout (personal preference; the content-style ban technically exempts dev-facing docs, but kept it consistent anyway).
- 2026-08-07: updated the deploy topology: `main` now auto-deploys to production behind a test gate, QA remains a manual deployment flow, and the `staging` pipeline has been removed.
