# Sprint map — LP Iterations ↔ web-team sprints

Internal lookup table. When someone on the web team or leadership references a
sprint by its **artist/letter name** (e.g. "what shipped in the Christina
Aguilera sprint?" or "Sprint F"), use this to find the matching **LP Iteration**
on board #75, then pull the work from #75 + git history.

## How it's keyed

- **Key on the letter, not the artist.** Web-team sprints are lettered
  alphabetically (A → B → C …) and the letter is known far in advance, so the
  map needs no retro/vote to stay current. The artist (voted at retro) is
  optional flavor — backfill it whenever, or never. "Web-team Sprint E 2026" is
  a perfectly stable identifier on its own.
- **Letters advance in lockstep with Iterations.** Both are 2-week and aligned
  on the same boundaries, so once anchored, `letter = anchor_letter + (N − anchor_N)`.
  Anchor: **LP Iteration 2 = Sprint E (Ed Sheeran)** — confirmed ground truth
  (E was the sprint that just finished; F is the one being planned now). This
  lets rows be pre-filled ahead of time.
- **Dates come from the #75 Iteration field** (authoritative), not the
  `vault.conf` sprint anchor — the two currently disagree by a day (board
  iterations start Tuesdays; the vault anchor is a Monday). Trust the board.

## Map

| LP Iteration | Dates (board #75)       | Web-team sprint | Artist     |
| ------------ | ----------------------- | --------------- | ---------- |
| 1            | 2026-05-12 → 2026-05-25 | D 2026 ⚠        | —          |
| 2            | 2026-05-26 → 2026-06-08 | E 2026          | Ed Sheeran |
| 3            | 2026-06-09 → 2026-06-22 | F 2026          | —          |
| 4            | 2026-06-23 → 2026-07-06 | G 2026          | —          |
| 5            | 2026-07-07 → 2026-07-20 | H 2026 ⚠        | —          |

⚠ = inferred by lockstep, not directly corroborated (D extrapolated backward,
H forward). E and F are confirmed ground truth; G is corroborated by #61's live
column. Confirm the ⚠ rows opportunistically; correct here if the web team ever
skips or merges a sprint (which would break the lockstep from that point on).

## Mirror & verify (#61)

LP's sprint lives on **#75 — that's the source of truth.** #61 (web team) gets a
courtesy **one-way push** of the committed items, tagged `Initiative = Justice
Initiatives`. #61 has no sprint/letter field, so our items land in `To Do` +
the JI tag — there's no "Sprint F" bucket on #61 holding them. The letter map
above is _name translation only_; it does not describe #61 placement.

**Push (per committed issue):**

```
board-mutate.py --issue N --status Ready --iteration <N> --mirror 61
```

`--mirror 61` adds the issue to #61 and sets Status (To Do) + Initiative
(Justice Initiatives) + Priority/Size (read from the issue's repo labels; the
matcher maps `P0`→`P0 🔥`, `S`→`S (1)`, etc.).

**First, do no harm.** The mirror is one-way and only ever touches the single
issue you push — never assignees, reviewers, or other items. #61 is allowed to
hold _more_ than #75 (we're not its sole owner); extra items there are **not**
drift to "fix." Flag stale JI items on #61 to a human; don't auto-clean.

**Verify parity** with the right filter — comparing the whole `To Do` column is
meaningless (it's the org-wide pile, 100+ items). The correct lens:

| Side | Filter                                             |
| ---- | -------------------------------------------------- |
| #75  | current Iteration                                  |
| #61  | `To Do` **and** `Initiative = Justice Initiatives` |

The two number-sets should be identical. (Pre-convention LP items may linger on
#61 untagged or under other initiatives — those are legacy debris, surfaced for
human cleanup, not parity failures.)

## Maintenance

- **When:** at sprint-commit (sprint boundary). Add the next Iteration row —
  the letter is already known, so this is a one-line append, no vote needed.
- **Artist column:** fill in if/when you happen to learn it; `—` is fine
  forever. The letter alone answers "what shipped in Sprint F" — the artist is
  just the friendlier handle people say out loud.
- **If the lockstep ever breaks** (web team skips/merges/renumbers): fix the
  divergent row and every row after it, and note the break.
