# Topic Flow Engine — Build Summary & Patterns

A post-build record of the Topic Flow engine: what it does, what we built, and
the engineering patterns that emerged worth carrying into the rest of the
codebase. Architectural rationale (linear-structure / open-contracts) lives in
[`ARCHITECTURE.md`](ARCHITECTURE.md); this doc is the "what we built and what we
learned" companion.

- **Epic:** [#389](https://github.com/freelawproject/litigant-portal/issues/389) — Topic Flow v1
- **Built across:** Iterations 2–3 (sprints E/F)
- **Lives in:** `litigant_portal/app/topic_flow/`

---

## What it is

A Topic Flow turns one court process — for one `(court, topic, role)` — into a
single, server-rendered page a self-represented litigant can read top to bottom:
what the process is, what facts to provide, what their personalized deadlines
are, and what to take with them (a calendar file, the clerk's contact card, the
list of forms to file).

It is the **non-AI engine**: every flow is authored content validated at the
boundary, with no LLM in the path. A court partner can author their own corpus
and stand up their own instance; the engine depends only on the data contract,
never on who produced it or how.

It works with **JavaScript disabled** — the whole flow is a `<form method="post">`
plus server-rendered sections, because our audience hits flaky networks, old
devices, and locked-down kiosks where a JS-only flow would strand them.

---

## What we built

Each capability landed as its own reviewed PR against the epic. In litigant
terms — _understand → tell us about your situation → here's what's true for you →
here's what to take with you_:

| Capability                    | What the litigant gets                                                                                                      | Refs                  |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| **Corpus contract + loader**  | A court's process authored as one validated YAML file; bad content fails loudly at deploy, never half-renders               | #479                  |
| **Section renderer**          | The page: info sections, fact-gathering forms, and outputs, in authored order                                               | #479 / PR #481        |
| **Answer persistence**        | Answers are remembered across the visit; you can leave a field, come back, and it's still there — no login                  | Item 5 / PR #493      |
| **Personalized deadlines**    | "Your response is due **Tuesday, March 3**" — computed from the dates you entered, not a generic "30 days"                  | #494 / PR #500        |
| **Add-to-calendar (.ics)**    | One tap drops your real deadlines into your phone's calendar                                                                | #504 / PR #507        |
| **Save-contact (.vcf)**       | One tap saves the clerk / legal-aid contact card to your phone                                                              | #473 / PR #508        |
| **Real corpus + track split** | The ND adult-name-change flow, from public sources, split into standard and waiver tracks selected by URL                   | #509 / PR #512        |
| **In-flow wayfinding**        | A table-of-contents menu and return-to-your-place-on-save, so moving back and forth to re-read or fix an answer is lossless | #510 / #511 / PR #513 |

---

## How it's built (at a glance)

```
content/*.yml
  → loader      parse → pydantic validate → cross-reference id checks
  → registry    index by (court, topic, role); skip bad files at runtime,
                fail loud at startup via a Django system check
  → renderer    section → RenderedSection (template + flat context); all
                section-type dispatch confined to one registry
  → answer_store  session-backed answers, namespaced per flow (guest-first)
  → deadlines / contacts   pure resolvers (no Django, no I/O)
  → artifacts   resolved data → .ics / .vcf bytes (vobject owns RFC escaping)
  → downloads   output_type → DownloadArtifact, via a second dispatch registry
  → views       two thin views: render the page, serve a download
```

Each module has a single responsibility and a docstring stating its contract
with the others. There is one test file per module plus the view.

---

## Patterns worth reusing

These surfaced during the build and are the parts most worth copying into other
features (and other FLP repos).

### 1. Validate at the boundary, then trust the data

The corpus is validated once, at load, in layers: pydantic with `extra="forbid"`
(an author's typo fails loudly instead of silently dropping data) → loader
cross-reference checks that span sibling lists (a deadline points at a real
question; an output points at a real deadline/contact) → a graceful runtime
registry (one bad file can't take down every flow) → a loud `manage.py check`
startup guard (the same failure surfaces at deploy). Everything downstream —
renderer, deadline math, artifact generation — assumes valid data and never
re-checks. **Push validation to one edge; keep the interior pure.**

### 2. One dispatch registry per axis; nothing downstream branches on type

Section rendering and file downloads each route through a single decorator
registry (`SECTION_RENDERERS`, `DOWNLOAD_HANDLERS`). No view, template, or
resolver contains `if section.kind == ...`. Adding a section type or a new
download format is **one registration**, not a hunt-and-patch across the
codebase. The download path was deliberately designed open-ended before the
first generator landed, so `.vcf` slotted in behind `.ics` with no new URL or
view code.

### 3. Share one resolver between the screen and the artifact

Anything shown on the page _and_ exported is resolved in exactly one place
(`resolve_ics_deadlines`, `resolve_vcf_contacts`), consumed by both the renderer
and the download handler. The downloaded calendar **cannot drift** from what the
litigant saw on screen — the invariant is structural, not a thing you remember
to keep in sync.

### 4. Keep the core Django-free and pure

renderer / deadlines / contacts / artifacts take plain data in and return plain
data or bytes out — no `request`, no session, no DB. They're unit-testable
without a database, and the field mapping for an `.ics`/`.vcf` is verified in
isolation. Session and request machinery live only in the two views and the
`AnswerStore`.

### 5. Progressive enhancement is the floor, not a nice-to-have

POST → persist → redirect (PRG), prefilled fields on the GET, native `<details>`
for the table of contents. The flow is fully usable with JS off; reactivity, if
any, only enhances. This is an org requirement for our audience, and the engine
honors it end to end.

### 6. Model multiple paths as separate corpora, not in-engine branching

The engine has no conditional logic — answers drive deadline math and display,
never which sections appear. A process with multiple procedural paths (name
change: standard vs. waiver; eviction: tenant vs. landlord) is modeled as
separate corpora chosen by distinct URLs, with the path decision pushed up to
the linking surface (the court links straight to the right track). This keeps
corpora authorable as plain content a legal reviewer can read top to bottom, and
keeps routing a human concern rather than engine logic. (Full rationale in
[`ARCHITECTURE.md`](ARCHITECTURE.md).)

---

## Known gaps & next

Surfaced during the build and the post-build review, and filed. Access-to-justice
framing throughout: nothing here should limit a litigant — or a self-hosting
partner — by device, operating system, or incomplete data.

**Content / linking** (the corpus surfaced these):

- Info-section bodies render as plain text — official-resource URLs and
  cross-track links aren't clickable ([#518](https://github.com/freelawproject/litigant-portal/issues/518), [#519](https://github.com/freelawproject/litigant-portal/issues/519)).
- Known-choice fields (e.g. county) are free text rather than a validated
  dropdown/autocomplete ([#514](https://github.com/freelawproject/litigant-portal/issues/514)).
- Real clerk/legal-aid phones and form PDFs still need a primary-source fetch
  ([#495](https://github.com/freelawproject/litigant-portal/issues/495)).

**Engine correctness / portability** (filed from the post-build review):

- `fact_gather` answers aren't validated on POST — empty required fields and
  out-of-set `choice` answers persist silently. Prerequisite for any document
  handoff ([#525](https://github.com/freelawproject/litigant-portal/issues/525)).
- Deadline date display uses POSIX-only `strftime("%-d")`, which crashes on
  non-POSIX hosts (e.g. a partner self-hosting on Windows) — an
  access-by-operating-system barrier ([#526](https://github.com/freelawproject/litigant-portal/issues/526)).
- The registry silently overwrites duplicate `(court, topic, role)` keys — the
  one place in the engine that fails silently instead of loud ([#527](https://github.com/freelawproject/litigant-portal/issues/527)).

**User-facing flow control:**

- Per-answer clearing and a "start over" affordance a litigant needs to correct
  their own data ([#515](https://github.com/freelawproject/litigant-portal/issues/515)).

**Up next — document assembly:** `packet` outputs list form _names_ only. The
next major capability is a warm handoff to a document-assembly tool
(docassemble) for the actual forms, with a return path back into the flow and
pre-submission answer checks. (Design in progress.)
