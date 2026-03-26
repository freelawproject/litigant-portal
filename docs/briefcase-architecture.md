# Briefcase Architecture: Three-Pocket Model

## Overview

The briefcase is the unified session state model for everything the portal knows about a user's situation. It has three "pockets" — raw data, working state, and analog/portable — so that data is never lost, the user experience is restorable, and warm handoffs to legal aid or analog processes work without our system.

---

## The Three Pockets

### Pocket 1: Raw Record (append-only event log)

**Purpose:** Immutable source of truth. Every input captured with full fidelity. If we change the RAG pipeline, legal flow, or AI models, we replay this log through the new system and lose nothing.

**Design principle: Pocket 1 is the test fixture for the pipeline.** If the RAG/agent processing is tight, re-feeding the same raw data from Pocket 1 through the pipeline should produce very nearly the same Pocket 2 and Pocket 3 outputs. This is functional testing for the legal flow — "Jane's raw inputs, processed through pipeline v2, should produce the same case facts, spotted issues, and action items as pipeline v1." This means:

- **Pocket 1 stores inputs, not outputs.** User messages, document content, user actions, and system context — not AI responses or tool call results. AI outputs are derived data that belong in Pocket 2.
- **Pipeline changes are testable.** Diff Pocket 2 outputs from old pipeline vs. new pipeline, using the same Pocket 1 inputs. Regressions are visible.
- **No circular data.** If AI outputs are in Pocket 1, replaying through a new pipeline mixes old AI reasoning with new — the test is meaningless.

**Storage:** Append-only event log. Each entry is timestamped and typed. Never modified or deleted (except by data retention policy or user deletion request).

**Event types (inputs only):**

- `user_message` — what the user typed, verbatim
- `document_upload` — file metadata + raw extracted text (the source content, not AI analysis)
- `user_action` — confirmed extraction, dismissed suggestion, marked item complete, corrected a fact
- `system_context` — topic entry, jurisdiction detection, session start/end, auth state change

**What it captures that Pocket 2 doesn't:**

- Superseded user inputs (user corrected a date — Pocket 2 has the correction, Pocket 1 has both the original and correction as separate events)
- Full conversation inputs (Pocket 2 may summarize for context window)
- Raw document text before AI extraction (the PDF content, not structured output)
- User decisions that shaped the flow (which prompt they clicked, what they confirmed/rejected)

---

### Pocket 2: Working State (mutable, restorable)

**Purpose:** Current state of the user's experience. What they see on screen, what the AI knows about them, what gets restored on login or briefcase import. This is the "save file."

**Contents:**

- **Case data** — case type, parties, court info, key dates
- **Spotted issues** — defenses, rights, legal theories the AI has identified
- **Action items** — next steps, deadlines, checklists with completion state
- **Eligibility** — programs the user qualifies for, application status
- **AI context** — conversation summary, memory/insights the AI needs to resume intelligently
- **Session metadata** — active topic, last interaction, conversation stage in legal flow
- **Timeline** — derived from Pocket 1 events, filtered/formatted for display

**Mutability:** Freely updated as the user progresses. Old states are recoverable from Pocket 1 replay.

**Persistence:**

- Authenticated users: saved to DB, restored on login
- Anonymous users: held in session, exportable as encrypted briefcase file
- Briefcase import: restores Pocket 2 state so the user picks up where they left off

---

### Pocket 3: Analog Package (hybrid: structured data + on-demand export)

**Purpose:** Everything a human needs to continue without our system. For warm handoff to legal aid, lawyer intake, or the user going to court with printed materials.

**Always maintained (structured data):**

- Forms in any state of completion (blank, partial, ready to file)
- Key deadlines and court dates
- Action items with current status
- Resource links and referral information
- Case summary in plain language

**Assembled on demand (export):**

- Full PDF/ZIP package combining the structured data above with:
  - Conversation highlights (key Q&A, not raw log)
  - Document summaries
  - Court logistics (address, parking, what to bring)
  - Legal issue summary with identified defenses/rights
- Formatted for: print, email, legal aid intake form, lawyer handoff

**Dual-audience clarity:** Plain language throughout, but never at the cost of legal precision. If Pockets 1 and 2 captured statutes, legal terms, form numbers, case citations, or procedural requirements, Pocket 3 preserves that detail — a lawyer or legal aid org reading the export should see the same specificity they'd expect from an intake file. Plain language supports and contextualizes the legal detail, it doesn't replace it. Example: "You need to file an Appearance (form IL-AP-001) — this tells the court you plan to contest the eviction, per 735 ILCS 5/2-201."

**Overlap with Pocket 2:** Pocket 3's structured data _is_ a subset of Pocket 2, maintained alongside it. The export assembler reads from Pocket 2 (current state) and selectively from Pocket 1 (conversation highlights, document content) to produce the package.

---

## Overlap Between Pockets

```
Pocket 1 (Raw Inputs)        Pipeline            Pocket 2 (Working)        Pocket 3 (Analog)
──────────────────────   ───────────────→   ──────────────────        ─────────────────
User messages                                AI summary/memory    ───→  Key Q&A highlights
Document text (raw)                          Current case facts   ───→  Case summary
User actions/decisions                       Spotted issues       ───→  Legal issue brief
System context                               Action items         ───→  Checklist + deadlines
                                             Timeline display     ───→  Court prep package
                                             Eligibility status   ───→  Program applications
                                             Form state           ───→  Forms (printable)
```

**Data flow:**

- Pocket 1 → Pipeline → Pocket 2 (inputs processed by AI/RAG into working state)
- Pocket 2 → Pocket 3 (working state filtered/formatted for analog use)
- Pocket 1 → _new_ Pipeline → Pocket 2' (replay test: same inputs, compare outputs)

**The replay guarantee:** `Pipeline(Pocket1) ≈ Pocket2`. If we change the pipeline and the outputs diverge beyond acceptable thresholds, that's a regression. Pocket 1 is the golden dataset.

---

## Anonymous Export

Full export includes all 3 pockets — the user gets complete fidelity. On re-import:

- Pocket 1 events are replayed/restored (immutable log intact)
- Pocket 2 state is restored directly (no reprocessing needed for immediate use)
- Pocket 3 structured data is restored alongside Pocket 2

Export format: encrypted JSON (or ZIP with JSON + any document files). The encryption key is user-provided or derived from a passphrase — we never store it.

---

## Open Questions (Not Covered Here)

- Django model definitions (depends on #197 schema research)
- Migration path from current CaseInfo/TimelineEvent
- Export file format specifics (encryption, compression, versioning)
- Multi-issue briefcases (eviction + child support in one briefcase)
- Data retention and deletion policies

---

## References

- [#177](https://github.com/freelawproject/litigant-portal/issues/177) — Briefcase issue
- [#197](https://github.com/freelawproject/litigant-portal/issues/197) — Schema research/POC
- [Happy Path](happy-path-jane.md) — Jane's end-to-end story
- [Legal Flow](overview-mapped-legal-flow.md) — 9-stage flow
- [Demo Strategy](demo-strategy.md) — how to demo the full flow before AI tools land
