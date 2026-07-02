# Sizing & estimation calibration

A living record for keeping our size → velocity mapping honest as the team
grows, and for banking what we learn each time we check estimates against
reality. This is the internal/tuning doc; contributors who just want to size
well should read [`sizing-guide.md`](sizing-guide.md).

## Why this exists

Velocity only means something to stakeholders if sizing maps to real delivered
work, and that mapping drifts — scopes change, the team changes, the tooling
changes. Sizing _ceremony_ (a room debating points) is theater on a small team;
the sizing _signal_ is worth keeping, but only if we periodically verify it and
adjust. This doc is where that verification lives.

## The three-level model

Estimation and its two verification passes measure different things — keep them
separate or the signal turns to mush:

| Level         | Look at                               | Measures               | Answers                             |
| ------------- | ------------------------------------- | ---------------------- | ----------------------------------- |
| **Estimate**  | The issue (at grooming)               | Forecast               | "How big do we think this is?"      |
| **Verify L1** | The PR diff **+ commit/PR narrative** | Item actuals           | "How much work was it _really_?"    |
| **Verify L2** | The iteration at close                | Commitment reliability | "Did we deliver what we committed?" |

- **Estimate vs L1** calibrates the **rubric** — are our per-item sizes accurate?
- **Committed vs L2** calibrates **capacity** — how much should we pull into a sprint?

Caveat for already-done work: you can only do **L1 cleanly** in hindsight (you
already know the outcome, so a retroactive "estimate" is contaminated). The full
clean loop — estimate at grooming, L1 from the PRs, L2 at close — starts on
work sized _before_ it's built.

## Scale & source of truth

The scale (XS 0.5 · S 1 · M 3 · L 5 · XL = split) and its point mapping live in
**`board-sync.py:SIZE_TO_ESTIMATE`** — the single place to re-scale (e.g. moving
to full Fibonacci) without relabeling anything. Size is the one human input at
grooming; Estimate auto-derives; the board sums Estimate per Iteration for
velocity. Priority/Size labels and board fields are kept in sync by
`board-sync.py --fix`.

## How to run a calibration pass

1. Pull board items (number, Iteration, Size, Estimate, Status) from board #75
   via the GraphQL `projectV2` items query.
2. For each done item missing a Size, bundle its **issue body + closing PR**
   (diffstat + PR body — join on the PR's `closingIssuesReferences`).
3. Size **L1** from the diff _and the narrative_, anchored to already-sized
   items in the same iteration — never from LOC alone.
4. (Optional, for learning) reconstruct an issue-only **estimate** and diff it
   against L1 — the gap is a proxy for **issue-description quality**, not a clean
   accuracy number.
5. Write sizes with `board-mutate.py --issue N --size X`, then
   `board-sync.py --fix` to derive Estimates and sync labels.

## Calibration log

### 2026-07-02 — It2–It4 baseline + It3 reconstruction

First pass. The board's Iteration field only starts at It2, so this is the
earliest point with real tracked data.

**Velocity (delivered points):**

| Iteration                  | Points                   | Merged PRs | Issues closed |
| -------------------------- | ------------------------ | ---------- | ------------- |
| It2 (05-26→06-08)          | 11.5                     | 18         | 24            |
| It3 (06-09→06-22)          | **20.5** (reconstructed) | 27         | 27            |
| It4 (06-23→07-07, partial) | 10.0                     | 14         | 19            |

It3 showed 6.5 on the board because 13 of its 18 done items were never sized.
Backfilling them (L1, +14 pts) flipped It3 from an apparent collapse to the
**biggest** iteration — which the sizing-independent throughput (27 PRs / 27
issues) had said all along. The points now agree with throughput; that agreement
is the point of the exercise.

**Lessons (backed by the item-level data):**

1. **Incident issues systematically under-size.** They're written _after_
   diagnosis, so the hard part sits in the "Cause" section as prose while the
   "Fix" is one line — reads XS, was S (#521, #522, #558). _Fix:_ size incident
   work at triage, when the diagnosis is the work.
2. **Diff ≠ effort — the textbook case is #555.** A 12-line diff, genuinely M:
   the work was authoring docassemble interviews, loading the Playground, and
   verifying both tracks end-to-end — none of it in the repo. LOC-based sizing
   would have been ~6× low. What saved it: the issue's DoD spelled out the real
   scope. Argument for reading the issue + narrative over the diffstat.
3. **Low resolution — almost everything lands S.** The scale is correctly
   effort-weighted (#504's 754-line `.ics` handoff is still an S), but if ~70%
   of items are S, points barely vary and the signal starts to feel like
   theater. Open question below.
4. **Issue quality is generally high** — 10 of 13 estimates matched actuals; the
   one real gap (#510) buried its actual logic (a question-id matcher) in a
   passing mention.

## Open tuning questions

- **Resolution:** split S (most work clusters there), or accept that most LP
  work is ~1-day units and treat velocity as roughly item-count?
- **Scale shape:** is 0.5 / 1 / 3 / 5 right, or move to full Fibonacci? (One
  line in `SIZE_TO_ESTIMATE`.)
- **Close the loop:** start the clean estimate → L1 → L2 cycle at It5 grooming —
  that's the first iteration where estimates exist _before_ the work, so it's
  the first real test of rubric accuracy rather than a reconstruction.
