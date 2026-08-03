# Contributing

Litigant Portal is an open-source access-to-justice project by [Free Law Project](https://free.law). Contributions are welcome — this page covers how work flows through the repo. Setup and quick start live in the [README](README.md).

## Workflow: issue → branch → PR → review

- **All work starts from an issue.** Check for an existing one first; file new issues through the [templates](.github/ISSUE_TEMPLATE) (blank issues are disabled). Full template and label conventions: [docs/wiki/issue-conventions.md](docs/wiki/issue-conventions.md).
- **One branch per issue**, named `{issue#}-{slug}` (e.g. `220-update-action-plan-tool`).
- **Open a draft PR early** — a pushed branch with a draft PR is the best place to discuss direction while work is in flight.
- **Every PR closes its issue** with a closing keyword ("Closes #220"). Keep PRs focused; one logical change per PR.
- **Ticket-specific acceptance criteria live on the issue**, on top of the repo-wide bar in [docs/wiki/definition-of-done.md](docs/wiki/definition-of-done.md). If you spot adjacent problems along the way, file them as new issues rather than growing the PR.
- **Priority and size** are assigned by the team during grooming — leave them off when filing.

## Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope?): description`, with types `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Imperative mood, atomic commits.

## Quality bar

**First-time setup:** `make install` (installs `pre-commit` and other dev tools via `uv sync --extra dev`) — required before `make lint` will run.

`make lint` and `make test` before pushing (`make pre-commit` runs both; pre-commit hooks also run on every commit). `make test` execs into the Django container, so `make docker` needs to be running first. What "done" actually requires — testing philosophy, WCAG/CSP/progressive-enhancement gates, content style, component discipline — lives in [docs/wiki/definition-of-done.md](docs/wiki/definition-of-done.md); that's the canonical bar for every PR and issue.

## Security

Report vulnerabilities through our [vulnerability disclosure policy](https://free.law/vulnerability-disclosure-policy/) (see [SECURITY.md](SECURITY.md)), not public issues.
