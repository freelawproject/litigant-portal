# Sizing in the zone

A two-minute guide to sizing an issue so the estimate tracks reality. If you're
tuning the scale itself or logging lessons, that's the companion doc:
[`sizing-calibration.md`](sizing-calibration.md).

## The scale

T-shirt sizes, calibrated to **AI-assisted** effort (one dev + an AI pair):

| Size | Points | Effort     | Feels like                                 |
| ---- | ------ | ---------- | ------------------------------------------ |
| XS   | 0.5    | ~1–2 hours | a focused change, one place                |
| S    | 1      | half a day | the workhorse — most issues land here      |
| M    | 3      | 1–2 days   | spans layers, or real novelty/coordination |
| L    | 5      | 3–4 days   | a full capability across data + API + UI   |
| XL   | —      | too big    | **stop and split into sub-issues**         |

Points are the same scale, 1:1 with size. You set the **Size**; the board
derives the **Estimate** number and sums it per iteration for velocity. The
mapping lives in one place — `board-sync.py:SIZE_TO_ESTIMATE` — so re-scaling is
a one-line change, never a relabel.

## Size the work, not the diff

This is the whole game. Lines changed is not effort:

- A **one-line fix that took three days** of debugging is not an XS. Size the
  diagnosis, not the patch.
- A **600-line mechanical rename** can be an XS.

So read the issue and the change, not the diffstat.

## Best practices — do these

1. **Size from a groomed issue.** If the issue is a one-liner, you can't
   estimate it — add scope first. A stub gets a guess, not an estimate.
2. **Size effort, novelty, and risk** — layers crossed (data / API / UI), how
   new the problem is, integration/deploy blast radius. Not LOC.
3. **Incident and debugging work: size the diagnosis.** Post-mortem issues make
   outages look trivial (the "Cause" is prose, the "Fix" is one line). The hard
   part already happened. Size it when the diagnosis _is_ the work.
4. **Count off-repo work.** Content authoring, infra/hosting setup, document-
   assembly interview design, end-to-end verification — none of it shows in the
   diff, all of it is effort.
5. **Size relative, not absolute.** Compare to the reference anchors below
   rather than reasoning from scratch. Consistency beats precision.
6. **XL is a beacon, not a size.** If it's XL, break it into sub-issues before
   it enters a sprint. Never commit an XL.
7. **An estimate is a forecast, not a promise.** It's not a commitment or a
   deadline, and velocity is a trend, not a contract.

## Reference anchors (real LP issues)

| Size | Example                                                                                                                                                                                                         |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| XS   | Drop a raw-slug breadcrumb line (#517) · add a `restart:` policy to prod services (#548)                                                                                                                        |
| S    | New download artifact + renderer on an existing seam — `.vcf` add-to-contacts (#473) · a CD disk-prune fix that took a live-outage diagnosis (#521)                                                             |
| M    | A decision record + coordination across sub-issues (#441) · wiring a handoff whose real work was authoring the docassemble interviews and verifying both tracks end-to-end (#555) — a 12-line diff, genuinely M |
| L    | A full new capability spanning data + API + UI with real novelty. (Recent iterations have skewed XS–M; when an L shows up, sanity-check it isn't a hidden XL.)                                                  |

## When in doubt

Pick the smaller size, note your reasoning in the issue, and let the
end-of-iteration review (delivered vs. committed) correct the scale over time.
The goal is a consistent yardstick, not a perfect one.
