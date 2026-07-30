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

## Contributor License Agreement (CLA)

Free Law Project requires a signed CLA before a PR can be merged. A bot checks this automatically on every PR.

- **Sign here:** [cla-assistant.io/freelawproject/litigant-portal](https://cla-assistant.io/freelawproject/litigant-portal) — one click via GitHub OAuth.
- **Already signed but the check still shows pending?** The CLA Assistant bot's comment on your PR includes a "Let us recheck it" link — click it to re-verify your signature against that PR.
- **What it is:** the [Apache Individual Contributor License Agreement V2.0](https://www.apache.org/licenses/icla.pdf), adapted with FLP's names. In return, FLP makes a public-benefit covenant: it "shall not use Your Contributions in a way that is contrary to the public benefit or inconsistent with universal access to public court documents."
- **You keep your copyright.** This is a license grant, not a copyright assignment — you're licensing FLP to use your contribution, not signing ownership over.
- **One signature, every FLP repo.** Sign once and it covers all `freelawproject` projects going forward, not just this one.

**Contributing on behalf of an employer?** The ICLA references an employer having "executed a separate Corporate CLA with the Project," but the repo has no documented contact or process for that path yet. If this applies to you, flag it on your PR or issue and we'll get you an answer before merge.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Participation in this repo — issues, PRs, discussions — means agreeing to abide by it.

## Security

Report vulnerabilities through our [vulnerability disclosure policy](https://free.law/vulnerability-disclosure-policy/) (see [SECURITY.md](SECURITY.md)), not public issues.
