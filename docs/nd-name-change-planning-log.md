# ND Adult Name Change — Demo Planning Log

Running digest of decisions and emerging patterns from planning the bespoke demo for the North Dakota Court System. Two purposes:

1. **For this demo** — single source of truth for decisions made during planning so later work (prompt doc, happy path, demo flow, implementation) can reference a coherent record.
2. **For future demos** — extract reusable patterns that are hard to see when in the trenches but obvious in hindsight.

## Context

- **Court partner:** North Dakota Court System. First demo landed 2026-04-20; ND followed up asking for Adult Name Change on QA — [#310](https://github.com/freelawproject/litigant-portal/issues/310).
- **Court's ask (paraphrased):** show how LP expands court capacity, reduces repeat-question friction on limited internal resources, and produces successful self-service outcomes, with reasonable human-in-the-loop escape hatches when needed.
- **Topic:** Adult Name Change (replaces expungement on the 6-topic grid for now; strong future-demo candidate for other courts).
- **AI mode:** prompting (not agentic tools) — abbreviated demo variant.
- **Template base:** [Jane's happy path](./happy-path-jane.md) (DuPage eviction).

## Personas

Jessica is writing the legal-grounded user stories; our flow design is built against them.

| Persona                      | Issue                                                                | Role in this work                                                              | Motivation                                                       | Track                                                  | Device                 | Privacy weight |
| ---------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------ | ---------------------- | -------------- |
| Sandra Eriksen, 54, Bismarck | [#311](https://github.com/freelawproject/litigant-portal/issues/311) | **Primary — happy path + featured demo narrative**                             | Post-divorce name restoration for passport application           | Standard (5 forms, publish, 30-day wait, $160)         | Desktop-first, evening | Low            |
| Alex, 26, Grand Forks        | [#312](https://github.com/freelawproject/litigant-portal/issues/312) | **Phase 2 stress-test** — used to tighten the flow after Sandra baseline lands | Transgender, changing first + middle name only, ahead of new job | Waiver (4 forms, no publication, no 30-day wait, $160) | Mobile, late night     | Very high      |

David Bowie → Ziggy Stardust was a pair-planning scaffold between Mitch and Claude before Jessica's personas landed; no longer canonical.

## Two Tracks

ND has two filing paths depending on what's being changed:

|                  | Standard track (Sandra)                                                                                      | Waiver track (Alex)                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Applies when     | Changing last name, or any combination that includes last name                                               | Changing first and/or middle name only — last name unchanged                                                               |
| Forms            | 5 — Notice of Petition for Name Change, Petition, Declaration, Confidential Information Form, proposed Order | 4 — Petition, Declaration, Confidential Information Form, proposed Order (Notice of Petition is not filed on waiver track) |
| Publication      | Required in county newspaper                                                                                 | Judge may waive; LP surfaces eligibility proactively                                                                       |
| Waiting period   | 30 days from publication                                                                                     | None on waiver track (if granted)                                                                                          |
| Filing fee       | $160                                                                                                         | $160                                                                                                                       |
| Hearing          | Discretionary; judge's call                                                                                  | Discretionary; judge's call                                                                                                |
| Citizenship      | Must be US citizen or permanent resident                                                                     | Same                                                                                                                       |
| Background check | Varies by judge — clerk contact pre-filing recommended                                                       | Same — and the waiver track doesn't eliminate this                                                                         |

The track is determined by the answer to Stage 2's load-bearing question: **what are you changing?** — not _why_ you're changing it.

## Headline Demo Beats

Story beats the demo is built around. These are what ND (and future courts) should walk away remembering.

- **Court-partner deep links work.** ND embeds a short URL on `ndcourts.gov/legal-self-help/name-change-adult` (or a county clerk page) that lands users directly in jurisdiction + topic context. Demonstrates the pattern any court can adopt on their existing self-help pages.
- **Catches the procedural misunderstanding.** Sandra arrives believing her divorce decree handled the name change. LP corrects this immediately and redirects her to the standalone-petition workflow without making her feel she failed. This is the "reduce repeat questions" proof point for standard-track users.
- **Proactive surfacing of gotchas.** Publication requirement, 30-day clock, background-check-timing question for the clerk, Confidential Information Form attachment requirement at order time. LP surfaces these concisely as checklists rather than waiting to be asked. Each catch is someone who would otherwise have come back to the clerk.
- **Resolution without account.** Sandra never creates a persistent account. Briefcase + magic link is enough — state persists, reminders fire, no auth wall.

Cross-device state portability (the earlier mobile→desktop→mobile arc) is **out of scope for this demo.** The desktop dashboard is the strongest surface for ND's demo; a mobile-first compressed UI is a later milestone. Magic-link state capture still exists as infrastructure but isn't a demoed beat.

## Architecture Decisions

### Stage 1 — Entry

| Decision                            | Choice                                                                                                                         | Rationale                                                                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| Arrival paths                       | Deep link OR topic-card click → same URL. Free-text triage routing skipped for this demo.                                      | Sandra finds LP via her county court's website; topic is pre-set by the link or by clicking "Adult Name Change" on the grid.            |
| Deep-link URL shape                 | `/t/north-dakota/adult-name-change` (canonical hyphenated slug per #338)                                                       | Court partners share/bookmark the human-readable slug; canonical slug used everywhere keeps the URL surface predictable.                |
| Court branding                      | ND Courts (and where possible the county, e.g. Burleigh) shown via feature flag / config, hot-swappable in QA without a deploy | Lets us demo different court partners without rebuilding. Ties to [#306](https://github.com/freelawproject/litigant-portal/issues/306). |
| Auth model                          | Magic-link handoff — deferred until reminders, cross-device sync, or state preservation are needed; never gates the product    | Mirrors Jane's "defer account to natural moment" principle. Sandra never needs a persistent account.                                    |
| State captured at magic-link moment | Full state — chat history, case facts, generated forms, deadlines, action items, uploaded docs                                 | One atomic capture at handoff is simpler than incremental sync.                                                                         |

### Stage 2 — Issue identification

| Decision                              | Choice                                                                                                                                                                                                              | Rationale                                                                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Opening tone                          | Outcome-framed, practical — "I'll help you get your name legally changed in North Dakota. To figure out the right path, I need to know a few things."                                                               | Topic is pre-set; no "what's going on?" needed.                                                                                         |
| Active-divorce check                  | LP asks early whether this is part of an active divorce case or a standalone petition. If divorce-bundled, LP explains that's handled inside the divorce paperwork and refers out.                                  | Catches Sandra's procedural misunderstanding without making her feel she failed. Standalone is the only path LP supports on this topic. |
| Track-forking question                | "What are you changing? First name, middle name, last name, or some combination?" Answer determines standard vs. waiver track.                                                                                      | This is the load-bearing question — not "why" but "what." Revealed by Alex's user story.                                                |
| Waiver surfacing                      | If answer is first and/or middle only (no last), LP immediately surfaces the publication waiver as a fact, with plain-language explanation of what it means practically and that the judge decides.                 | Load-bearing for Alex-type users; surfacing it late or reactively is a product failure.                                                 |
| Don't ask "why"                       | LP never asks the reason for a name change                                                                                                                                                                          | We inform, we don't advise. The reason isn't LP's business.                                                                             |
| Self-classification via inform-first  | Present ND's categories and waiver rules as facts; let the user self-classify                                                                                                                                       | Avoids interrogation; respects that users arrived here to do something.                                                                 |
| Escalation ladder when user is unsure | 1. Present facts, no question. 2. If still unsure, offer help and note the ask requires more info — paired with privacy commitment. 3. If still unsure, ask for the specifics needed (privacy commitment repeated). | Inverts intake-form gatekeeper pattern. Asks only when user signals they need help.                                                     |
| Disqualifier framing                  | "These conditions can prevent a name change in ND" — presented as facts for self-attestation                                                                                                                        | Never interrogate. Present the rule; let users apply it to themselves. Citizenship requirement is one of these.                         |
| Publication requirement               | Assume standard-track users must publish. Phase-2 tightening with Alex adds the waiver track's publication-waived path.                                                                                             | This is a new-topic happy path. Standard-track baseline first.                                                                          |
| Sandra's path through Stage 2         | Active-divorce check: standalone. Track fork: standard (restoring last name). No disqualifiers.                                                                                                                     | Flows straight through.                                                                                                                 |

### Stage 3 — Issue & document discovery

| Decision                            | Choice                                                                                                                                                                                                            | Rationale                                                                                                                                                                      |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Full-picture narration              | One structured message at Stage 3 open — process arc, forms, fees, publication, wait, hearing possibility, order, cascade tease, timeline. Sidebar populates concurrently.                                        | "Can I actually do this?" is the question users ask themselves early. Honest upfront = trust = fewer drop-offs.                                                                |
| Sandra's county                     | Assume Burleigh County (from #311). Confirmed as part of Stage 3 narration; no input required.                                                                                                                    | She arrived via her county court's site; jurisdiction is grounded.                                                                                                             |
| Sidebar item structure              | **Flat** — each step is one line, with an expando for info only. No sub-checklists, no nested checkboxes.                                                                                                         | Keep it simple. Clutter hides the path.                                                                                                                                        |
| Checklist as a separate deliverable | Offer a **printable checklist** (with boxes + substeps) as an option the user can request. Not the in-app pattern.                                                                                                | Printable artifacts serve a different purpose than the live sidebar. Users who want the tangible list can have it; the live product stays clean.                               |
| Blocker handling                    | Pre-filing blockers (e.g., Burleigh Clerk call about background-check timing) surface **twice**: once in the Stage 3 narration at the very start, and permanently at the top of the sidebar labeled as a blocker. | Blockers that moot other progress must be unmissable. Not hidden under a checklist item further down.                                                                          |
| Proactively surface as facts        | Fee waiver criteria, publication waiver criteria (why it doesn't apply to Sandra), citizenship requirement, 6–8 week minimum timeline                                                                             | Inform-first pattern. Sandra leaves Stage 3 knowing what she's signing up for and why alternatives (waiver, fast track) don't apply to her.                                    |
| End-goal threading                  | LP mentions Sandra's passport once in Stage 3 as a tease ("your passport comes after SSA and DMV — we'll sequence that at the end"), full cascade in Stage 9.                                                     | LP gives info _and_ holds the end goal in context. User feels seen rather than funneled through generic steps.                                                                 |
| Progress / navigation UX            | A progress bar across the bottom of the main nav shows all steps, clickable to drill into any step's detail, then back to the dashboard.                                                                          | Non-modal, persistent context. Gives Sandra spatial awareness of the whole path without leaving her place. _(UX pattern that applies beyond this topic; likely its own epic.)_ |

**Sidebar for Sandra at Stage 3:**

Top of sidebar (blocker):

- ⚠️ Call Burleigh County Clerk about background-check timing _(expando: what to ask, phone number)_

Then the flat path:

- Prepare 5 forms _(expando: what each form does)_
- Pay $160 filing fee _(expando: fee waiver info if applicable)_
- Publish notice in Burleigh County newspaper _(expando: what publication means, who qualifies for waiver)_
- Wait 30 days from publication
- Possible hearing _(expando: not required by default; judge's discretion)_
- Receive Order + certified copies _(expando: request at least 3; Confidential Info Form must attach to each)_
- Update your records _(expando: SSA first, then DMV, then passport, banks, employer, insurance, home title)_

### Stage 4 — Related issue surfacing

| Decision                        | Choice                                                                                                                                                                                     | Rationale                                                                                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Weight for this topic           | **Thin confirmation beat** — not a rich surfacing round                                                                                                                                    | Sandra's situation is narrow and clean; related issues are limited.                                                                                       |
| Scope-adjacent items            | Track silently throughout Stages 3–5 (voter registration, property title, will/POA, etc.); surface at the end (Stage 9) rather than mid-flow                                               | Keeps the core flow focused. Sandra decides whether to engage with adjacent items after her primary goal is resolved.                                     |
| Framing of scope-adjacent items | **Facts, not recommendations.** Mention as "name change will leave your property deed in your married name" — never "you should update your deed." Link out to resources; let user decide. | Info, not advice. Same principle as disqualifier framing; respects autonomy and keeps LP from overstepping.                                               |
| "Anything else?" prompt         | Not in happy path                                                                                                                                                                          | Inform-first. LP doesn't invite user-initiated additions during the clean flow. Future personas with stacked issues may warrant this, but not for Sandra. |
| Sandra's Stage 4                | LP says "here's what we're covering — a standalone name-change petition in Burleigh County restoring your name to Sandra Eriksen, with the records cascade at the end. Sound right?"       | Confirms scope, names the end goal, gives Sandra one beat to redirect if anything's off.                                                                  |

### Stage 5 — Guided next steps

| Decision                     | Choice                                                                                                                                                                                                                                                                       | Rationale                                                                                                                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Form assembly mechanics      | **Pinned — not decided in this pass.** Varies by court, varies by topic, needs its own design pass. For Sandra's demo, treat the 5 forms as a pre-filled bundle surfaced as PDFs.                                                                                            | Document assembly is a whole side topic. Designing it inline here would derail this flow's planning without resolving it properly.                      |
| Form preview UI              | Assembled PDF opens in a new tab; user prints or downloads. No custom in-app form-preview component.                                                                                                                                                                         | Emulates what a future doc-assembly tool or court e-file integration would deliver. Don't build interim tooling that won't survive.                     |
| Clerk call — data capture    | LP offers Sandra two modes: (a) **live notes input** while she's on the call (typed-in capture), (b) **paste or doc upload** if she already took notes elsewhere. LP never makes her type the same thing twice.                                                              | If LP can receive the clerk's answer, it updates the case context (e.g., adds "complete background check" as an upfront step if ordered before filing). |
| Publication logistics        | LP lists qualifying Burleigh County papers (names + phone/email + cost range) **and** generates the Notice text pre-filled with Sandra's details, ready to paste into an email to the paper.                                                                                 | Concrete "reduce friction" beat. ND's ask is literally this kind of thing.                                                                              |
| Deadline math                | Placeholder dates until real dates exist, then hydrate. Sidebar shows "Earliest judge review: ~35 days after publication" until Sandra confirms publication, then shifts to actual calculated dates.                                                                         | Live recalc once real dates flow in; honest estimates until then.                                                                                       |
| Fee waiver handling          | Stated as fact in Stage 3 (inform-first). In Stage 5, LP walks Sandra through the waiver form only if she chooses to explore — no proactive prompt.                                                                                                                          | Respects autonomy. User applies the rule to themselves.                                                                                                 |
| Sandra's Stage 5 throughline | Pre-filled forms as PDFs → call Burleigh Clerk (LP offers to take notes live) → clerk answer updates path → LP gives publication paper list + pre-filled Notice text → Sandra submits Notice → publication date confirmed → deadline math hydrates → file packet with clerk. | All five concrete deliverables that remove the real-world friction points in Sandra's #311 narrative.                                                   |

### Stage 6 — Warm handoff

| Decision                          | Choice                                                                                                                                                   | Rationale                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Scope                             | **Flag-only** — mark spots in the flow where handoff _could_ happen, don't implement routing                                                             | Sandra's happy path doesn't take any handoff.                                                      |
| Court-informed design             | Handoff behavior should be informed by ND's FAQ / existing support patterns. Ask the court what they want LP to do at those spots.                       | Different courts have different support capacity. LP's handoff logic maps to what the court wants. |
| Candidate spots for Sandra's flow | Form-field confusion → ND Legal Self Help Center. Divorce-interaction questions → legal aid. Income-adjacent questions → Legal Services of North Dakota. | Marked with `{HANDOFF}` in the eventual prompt doc; live placeholders, not wired routes.           |

### Stage 7 — Handoff re-integration

| Decision                 | Choice                                                                                                                                                                                       | Rationale                                 |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Scope                    | Flag-only for this demo                                                                                                                                                                      | No handoffs taken in Sandra's happy path. |
| Pattern when implemented | Reuse the "don't make user re-enter" capture modes from Stage 5 (live notes, paste, upload). External info flows back through the same ingestion pattern, wherever the user was in the flow. | Already decided; no new mechanism needed. |

### Stage 8 — File or appear

| Decision                        | Choice                                                                                                                                        | Rationale                                                                                     |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Filing path for demo            | **Paper filing only** — download/print assembled PDF packet, take to Burleigh County Clerk in person                                          | Demo scope. No e-file or mail variants for this pass. Keeps the implementation surface small. |
| Court-visit plan                | LP generates a Jane-style visit plan: Burleigh Clerk address, hours, parking, what to bring, fee payment format, what to expect at the window | Concrete artifact that travels well in the demo.                                              |
| Pre-filing reminders (restated) | Case number blank. Don't sign the Order. Confidential Info Form attaches to the Order.                                                        | From #311; non-negotiable ND-specific procedural points.                                      |

### Stage 9 — Resolution & follow-up

| Decision                        | Choice                                                                                                                                                                                         | Rationale                                                                                                       |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Post-publication reminder       | LP fires a reminder when the 30-day publication window elapses, prompting Sandra to check in with the clerk about judge review                                                                 | Keeps her from forgetting and drifting.                                                                         |
| Cascade sequencing              | **Standard ND sequence** for all users — SSA → DMV → passport → financial accounts → employer → health insurance → home title → voter registration. Not personalized to the user's motivation. | Personalized sequencing is a future warm-fuzzy, not load-bearing for the demo. Sandra knows her own priorities. |
| Scope-adjacent items at the end | Tracked through the flow (from Stage 4's silent collection); surface as facts-with-links here, not recommendations                                                                             | Info, not advice.                                                                                               |
| Reminder delivery               | Email + SMS as options (either / both). **Likely already a separate feature issue** — flag as out-of-scope for this planning pass.                                                             | Notification infrastructure is its own track.                                                                   |
| "Done is done"                  | **Open question — court's call.** LP provides mechanisms (state persistence, magic-link reopen, explicit "I'm done" affordance); courts choose the policy.                                     | Different courts may want different end-of-flow behavior. Ask ND as part of demo follow-up.                     |

## Demo Scope — "Working, but fixtured"

The goal of this demo is **not** to ship the full name-change product. It is to show the happy-path experience end-to-end with working UI, working navigation, working data persistence — and **fixture-backed intelligence** where full agentic/AI depth isn't needed yet.

- Buttons work. Forms render. Sidebar updates. Magic link persists state (fixture-backed is fine — doesn't need full auth infrastructure).
- Prompts can be static or lightly templated; full agentic reasoning is not the demo. This is a **prompting** flow, not an agentic-tools flow.
- Court-specific content (ND language, Burleigh details, paper list, Notice text) lives in the prompt doc and can be hardcoded for this demo.
- "Things should actually work" — no dead ends, no "coming soon," no placeholder CTAs. If Sandra would click it in real life, the demo shows what happens.

This pattern — real infrastructure, fixture intelligence — is explicitly part of the plan so that implementation doesn't overreach into full AI/agentic work that isn't the milestone.

## Phase-2 Tightening with Alex ([#312](https://github.com/freelawproject/litigant-portal/issues/312))

Decisions to revisit after Sandra's baseline lands. Alex's user story stress-tests:

- **Waiver track** as a first-class path — Stage 2 fork, Stage 3 form list adjusted (4 forms, no Notice of Petition), Stage 5 timeline adjusted (no 30-day wait)
- **Public-record transparency** — what's in the public file vs. the sealed Confidential Information Form. Surface proactively, before the user asks.
- **Declaration guidance without compelled disclosure** — offer legally sufficient examples ("to better reflect my identity," "personal preference") and stop there. Don't probe.
- **Consistent identity handling** — "current legal name" / "requested name" only. Never "real name," "birth name," or "given name."
- **Scope boundary at gender marker** — acknowledge the connection, refer out to ND Legal Self Help Center and a legal aid organization, do not attempt to navigate.
- **No-hearing-preferred UX** — be honest a hearing is possible, explain conditions, don't falsely reassure.

## Reusable Patterns (emerging)

Patterns likely to apply beyond this demo. Extract to a playbook once 2–3 bespoke demos have been planned this way.

- **Single canonical topic URL.** Deep link from a court-partner site and topic-card click from LP home resolve to the same URL. One route, multiple entry points.
- **Court config as data, not code.** Court name, branding, jurisdictional corpus should be config so QA can hot-swap partners without a deploy.
- **Magic-link auth as state-portability primitive.** Not "sign up," not "create account" — "continue where you left off." Lowers friction, matches pro-se mental model.
- **Proactive gotcha-surfacing is the value prop courts care about.** What courts notice isn't "AI answers questions" — it's "AI catches the thing the user was going to miss and come back about."
- **Procedural-misunderstanding catch.** Users often arrive with a confident but incorrect assumption about what their previous court interaction covered. LP's job is to correct this gently, early, and redirect without punishing the user for the misunderstanding.
- **"What" before "why".** The load-bearing question that forks flows is almost always about what the user is doing, not why. Asking why feels like interrogation and is rarely legally necessary.
- **Inform-first over intake-first.** Present rules and categories as facts; let users self-classify and self-attest. Only ask probing questions if the user signals they need help, and pair the ask with a privacy commitment every time. Biggest ethos difference between LP and a typical court intake tool.
- **Disqualifiers as information, not interrogation.** "These conditions prevent X" — not "are you one of these."
- **Escalation ladder for information gathering.** Inform → offer to help → ask for specifics, with a privacy commitment introduced whenever help or specifics enter the picture.
- **Every topic + court needs a scoped prompt doc.** Jane has a DuPage prompt; Sandra will need an ND-Adult-Name-Change prompt. The prompt doc is where jurisdictional corpus and court-specific instructions live.
- **Blockers ≠ traps.** Things that moot further progress (background-check-timing question, identity-verification steps, payment before filing) are **blockers**, framed neutrally. They surface at the very start of a stage and pin to the top of the sidebar. Never buried in a mid-list checklist item. "Trap" is internal-team shorthand that doesn't belong in user-facing framing.
- **Flat sidebar, info-only expandos.** Don't nest checklists. Each step is one line; expando reveals explanation. Checkboxes for multi-step progress tracking belong on an optional printable artifact, not in the live sidebar.
- **End-goal threading.** LP holds the user's motivation throughout and references it at sequencing-critical moments ("your passport comes after SSA and DMV"). The product gives information _and_ sees the user. Differentiates from a generic info site.
- **Progress bar as bottom-of-nav navigation.** Step-wise progress lives in a persistent, clickable path strip at the bottom of the main nav. Users drill into any step for detail, return to the dashboard without losing their place. Non-modal, always visible, scannable. _(UX pattern worth its own epic once validated in this demo.)_
- **Info, not advice.** Always frame scope-adjacent items as facts ("this will still be in your married name"), never as recommendations ("you should update this"). Link out to resources; let the user decide. Same shape as disqualifier framing and "what before why" — LP is a librarian, not an advisor.
- **Phases are invariant; sub-stages flex with topic.** The three phases (Triage / Prepare / Resolve) exist in every legal flow. Sub-stages within each phase can grow, shrink, be reordered, or be replaced entirely depending on the topic — and even within a single topic, their weight can vary based on what a given user's situation surfaces. The 9-stage generic flow in `overview-mapped-legal-flow.md` is a template, not a mandate.
- **Don't make the user re-enter.** When an external action produces information LP needs (phone call, email reply, external form), offer multiple capture modes — live notes input during the action, paste, upload. Never force the user to retype what they've already written down.
- **Emulate future integrations with simpler artifacts.** When the target UX is a deep integration (doc-assembly tool, court e-file API, background-check API), a PDF in a new tab or an email with pre-filled text is sufficient for demos and early milestones. Don't build interim tooling that won't survive the integration work. The "future" artifact is the shape; today's demo uses the simplest thing that communicates that shape.
- **Pin, don't solve.** When a design decision varies by court or topic and isn't load-bearing for the current milestone, capture the open decision explicitly in the planning log and move on. Form assembly, e-filing, and court-integration mechanics are all pinned in this demo.
- **Working, but fixtured.** Demo milestones should have _working_ infrastructure — buttons trigger real code paths, real templates render, sidebar state persists, navigation is honest — with **fixture-backed intelligence** where full agentic/AI depth isn't needed yet. Hardcoded prompts, canned court content, mocked AI responses are fine; dead-end CTAs and "coming soon" placeholders are not. Work → Right → Fast ordering that lets us ship visible progress while keeping backend honest.
- **Courts inform their own handoff logic.** When to refer users out, where to refer, and how to frame it should be informed by the court partner's own FAQ / support patterns — not designed in isolation. Each court has different support capacity and LP's handoff behavior should map to it. Ask the court rather than guessing.
- **"Done" is a court policy, not a product default.** When the user's LP session ends, whether state persists indefinitely, and whether the magic link can reopen are all court-by-court policy questions. LP provides mechanisms; courts choose how to use them.

## Open Questions / Flags

- **Human-in-the-loop handoff points** (Stages 6–7) — noted to flag inline where these plug in, but not implemented for this demo.
- **Custom prompt doc location + structure** — mirrors Jane's DuPage prompt; filename and structure TBD once we land on a convention.
- **Privacy commitment copy** — the escalation ladder references a privacy commitment that needs to exist as ownable, user-facing copy. TBD where it lives (own page, inline disclosure, link target).
- **Publication waiver specifics** — confirm ND's exact statutory criteria for waiver (phase 2 with Alex). Sandra's story notes she doesn't qualify because she's restoring last name — last-name changes categorically require publication, first/middle-only can be waived.
- **Sandra's county filing details** — Burleigh County Clerk of Court. Pre-filing clerk contact for background-check timing is a named procedural trap in #311 and should be built into the flow.
- **Post-order cascade sequencing** — SSA before DMV is load-bearing (SSA change enables the DMV change). Confidential Information Form must attach to the certified Order or ND Vital Records rejects. Both are phase-2 refinements but worth noting now.

## References

- [Issue #310](https://github.com/freelawproject/litigant-portal/issues/310) — ND court ask (Adult Name Change on QA)
- [Issue #311](https://github.com/freelawproject/litigant-portal/issues/311) — Sandra user story (standard track, post-divorce restoration)
- [Issue #312](https://github.com/freelawproject/litigant-portal/issues/312) — Alex user story (waiver track, privacy-weighted)
- [Jane's happy path](./happy-path-jane.md) — template base
- [Legal flow overview](./overview-mapped-legal-flow.md) — 9-stage generic flow
- [Jane demo flow](./demo-flow-jane.md) — abbreviated pattern reference
- ND Courts Name Change landing: https://www.ndcourts.gov/legal-self-help/name-change-adult
- ND Forms + Instructions PDF: linked on [#310](https://github.com/freelawproject/litigant-portal/issues/310)
