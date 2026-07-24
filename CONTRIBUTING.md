# Contributing

Litigant Portal is an open-source access-to-justice project by [Free Law Project](https://free.law). Contributions are welcome — this page covers how work flows through the repo. Setup and quick start live in the [README](README.md).

## Workflow: issue → branch → PR → review

- **All work starts from an issue.** Check for an existing one first; file new issues through the [templates](.github/ISSUE_TEMPLATE) (blank issues are disabled). Full template and label conventions: [docs/wiki/issue-conventions.md](docs/wiki/issue-conventions.md).
- **One branch per issue**, named `{issue#}-{slug}` (e.g. `220-update-action-plan-tool`).
- **Open a draft PR early** — a pushed branch with a draft PR is the best place to discuss direction while work is in flight.
- **Every PR closes its issue** with a closing keyword ("Closes #220"). Keep PRs focused; one logical change per PR.
- **Definition of done lives on the issue.** Scoped issues carry a DoD checklist; the checklist is what "done" means. If you spot adjacent problems along the way, file them as new issues rather than growing the PR.
- **Priority and size** are assigned by the team during grooming — leave them off when filing.

## Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope?): description`, with types `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Imperative mood, atomic commits.

## Quality bar

- `make lint` and `make test` before pushing (`make pre-commit` runs both; pre-commit hooks also run on every commit).
- **Test our code, not libraries** — tests should fail when our logic breaks, not assert static copy or framework behavior.
- **WCAG 2.2 AA is a hard requirement**, not a target: [docs/wiki/wcag-strategy.md](docs/wiki/wcag-strategy.md).
- **CSP compliance:** no inline event handlers (a pre-commit hook blocks them); Alpine.js CSP build patterns only.
- **Progressive enhancement:** base workflows work without JavaScript — our users are on flaky networks, old devices, and courthouse kiosks.

## Security

Report vulnerabilities through our [vulnerability disclosure policy](https://free.law/vulnerability-disclosure-policy/) (see [SECURITY.md](SECURITY.md)), not public issues.
