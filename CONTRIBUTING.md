# Contributing

Litigant Portal is an open-source access-to-justice project by [Free Law Project](https://free.law). Contributions are welcome — this page covers how work flows through the repo. Setup and quick start live in the [README](README.md).

## Workflow: issue → branch → PR → review

- **All work starts from an issue.** Check for an existing one first; file new issues through the [templates](.github/ISSUE_TEMPLATE) (blank issues are disabled). Full template and label conventions: [docs/wiki/issue-conventions.md](docs/wiki/issue-conventions.md).
- **One branch per issue**, named `{issue#}-{slug}` (e.g. `220-update-action-plan-tool`).
- **Open a draft PR early** — a pushed branch with a draft PR is the best place to discuss direction while work is in flight.
- **Every PR closes its issue** with a closing keyword ("Closes #220"). Keep PRs focused; one logical change per PR.
- **Ticket-specific acceptance criteria live on the issue**, on top of the repo-wide bar in [docs/wiki/definition-of-done.md](docs/wiki/definition-of-done.md). If you spot adjacent problems along the way, file them as new issues rather than growing the PR.
- **Priority and size** are assigned by the team during grooming — leave them off when filing.

### Review: the assignee is the baton

CODEOWNERS and review requests say who _may_ review a PR. The **assignee** says whose turn it is right now. One person holds the PR at a time, and every hand-off is explicit:

1. A dev pushes a branch and opens the PR. Review requests go out automatically; the filer may also ask someone directly.
2. **Whoever takes the review assigns themselves.** If the filer asked someone directly, the filer assigns that dev instead. Until someone is assigned, the review is unclaimed.
3. The reviewer reviews, then requests changes or approves.
4. **The PR goes back to the filer** — reassign it to them.
5. The filer makes the changes and **assigns it back to the reviewer**. Repeat from step 3 until the review is settled.
6. The PR ends clean with the **original filer as assignee**. With CI passing, **the filer merges their own PR.**

Two things that are easy to get wrong:

- **Approving is not the end of your turn.** Hand the PR back by reassigning it. An approved PR still sitting with the reviewer reads as unfinished work.
- **Don't merge someone else's PR.** Reviewing is the reviewer's job; merging is the filer's. A PR you approved is not yours to land.

A PR with no assignee is waiting for a reviewer to claim it — a normal state right after opening, not drift.

Note the contrast with issues, which are **claimed** rather than handed off: you assign yourself an issue when you start work on it. PR assignment is a turn indicator, not ownership.

## How work is tracked

Work is tracked on the [Sprint (Litigant Portal)](https://github.com/orgs/freelawproject/projects/75) board, which is public — anyone can read it without being a member.

**Assignment.** Issues are assigned when someone starts work, not when they're filed. Unassigned is normal and legitimate, including for work in the current iteration. `good first issue` and `help wanted` are never pre-assigned.

**Iterations.** Sprints are two-week iterations on the board, identified by number and date range (e.g. "Iteration 9 · Sep 1–14"). An iteration is a record of what was committed and what shipped, so unplanned work that lands inside the window is folded in, and the committed total is recorded at close before any carry-over moves. Unfinished work returns to Backlog and is re-placed at the next planning session, never auto-rolled into a future iteration.

**Status.** The Iteration field records commitment. Status records where the work is.

| Status      | Meaning                                                                             |
| ----------- | ----------------------------------------------------------------------------------- |
| Backlog     | Not committed to an iteration. No Iteration set; size and priority not required.    |
| Ready       | Committed to the current iteration, not started. Iteration, size, and priority set. |
| In progress | Being worked on now.                                                                |
| In review   | PR open, awaiting review.                                                           |
| Done        | PR merged or issue closed.                                                          |

Size and priority are the gate to _leave_ Backlog, not to enter it — an issue can be filed and sit there untriaged. Work placed in a future iteration stays in Backlog until that iteration opens. Issues that aren't units of work at all (decision records, research threads, open questions) live in Backlog permanently and are never sized.

**Priority and size live on the issue as labels** (`P0`–`P3`, `size: XS` through `size: XL`), set during grooming. The board mirrors them into its own Priority and Size fields, because a project board can't group or sort by label. The labels are the source of truth — edit those, not the board fields.

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
- **What you're asserting.** Signing represents that each contribution is your own work and that you have the right to license it.
- **You keep your copyright.** This is a license grant, not a copyright assignment — you're licensing FLP to use your contribution, not signing ownership over.
- **One signature, every FLP repo.** Sign once and it covers all `freelawproject` projects going forward, not just this one.

**Contributing on behalf of an employer?** The ICLA references an employer having "executed a separate Corporate CLA with the Project," but the repo has no documented contact or process for that path yet. If this applies to you, flag it on your PR or issue and we'll get you an answer before merge.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Participation in this repo — issues, PRs, discussions — means agreeing to abide by it.

## Security

Report vulnerabilities through our [vulnerability disclosure policy](https://free.law/vulnerability-disclosure-policy/) (see [SECURITY.md](SECURITY.md)), not public issues.
