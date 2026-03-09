# Legal Flow

## Purpose & Audience

This document describes the stages any litigant moves through when using the portal — regardless of case type, AI mode, or authentication state. It is a design reference and legal review artifact, not an implementation spec. Legal reviewers can use it to understand what the portal does at each stage (UX behavior and high-level tooling) before reviewing specific content, disclosures, or data flows. Developers and designers can use it as a canonical map when building or extending features. The flow is not linear: stages can be revisited, skipped, or repeated as a user's situation evolves. The document is intentionally technology-agnostic — specific AI behavior, prompts, and database design are out of scope.

---

## Non-Linearity

Users rarely move cleanly from start to finish. The most common loops:

- **Triage → Triage:** A user describes their situation, an answer surfaces a new issue they hadn't considered, and they return to the beginning to re-identify what they're actually dealing with.
- **Prepare → Warm Handoff → Prepare:** A user connects with legal aid or a guided interview tool, receives new information, and returns to the portal with updated facts or documents.
- **Resolve → Prepare:** A filing is rejected or a court date is continued. The user re-enters at the preparation stage with new constraints.
- **Court Visit → Triage:** A user leaves for court and returns with a changed situation — a new order, a counterclaim, a negotiated agreement — and re-enters at the beginning with existing case context intact.

The portal must not assume forward progress. State must be preserved across exits and re-entries at any stage.

---

## The Legal Flow

Stages are grouped into three phases: **Triage**, **Prepare**, and **Resolve**.

### Phase 1: Triage — "What's my situation?"

| Stage | Name | Description | UX Expectation | Tooling (high-level) |
|-------|------|-------------|----------------|----------------------|
| 1 | Entry | First load or referral via court, legal aid, or community link | No friction; county auto-detected where possible; open chat or topic grid depending on mode | Portal routing, county detection |
| 2 | Issue identification | User describes their situation in their own words | One question at a time; plain language; no jargon; no account required | AI conversation / topic browse |
| 3 | Issue & document discovery | Specific legal issue confirmed; relevant documents surfaced | Clarifying questions about notice type, case stage, and key facts; documents can be uploaded | AI conversation, document upload |
| 4 | Related issue surfacing | Connected issues identified proactively or via browse | Sidebar or action list updated; AI may raise issues the user did not mention | AI proactive connection / topic browse |

### Phase 2: Prepare — "What do I need to do?"

| Stage | Name | Description | UX Expectation | Tooling (high-level) |
|-------|------|-------------|----------------|----------------------|
| 5 | Guided next steps | Deadlines, filing requirements, and action items assembled | Sidebar or checklist shows what is needed and when; nothing buried in conversation history | Deadline calculator, case sidebar / portable case file |
| 6 | Warm handoff | User connected to legal aid, guided interview tool, or court self-help resource | Handoff is optional and user-initiated; case context travels with the user | Legal aid referral, guided interview tool (e.g. DocAssemble), court resource links |
| 7 | Handoff re-integration | New information from external tool or attorney flows back into the portal | Portal accepts returning user and updates case facts, deadlines, or documents accordingly | Case file import / session resume |

### Phase 3: Resolve — "Take action"

| Stage | Name | Description | UX Expectation | Tooling (high-level) |
|-------|------|-------------|----------------|----------------------|
| 8 | File or appear | E-file, download forms, or prepare for court visit | Multiple resolution paths offered; user chooses; no dead ends | E-filing system, form download, court logistics info |
| 9 | Resolution & follow-up | Confirmation of filing, reminders, case history, post-resolution next steps | Confirmation is immediate; reminders are set; case is not abandoned after filing | Email/SMS notifications, case history, deadline reminders |

---

## Jane's Story — Mapping to the Flow

The ITC demo uses Jane, a self-represented litigant facing eviction. Her path through the stages:

| Stage | Jane's Moment |
|-------|---------------|
| 1. Entry | Opens the portal on her phone; no account |
| 2. Issue identification | "I got eviction papers" — AI classifies: 5-day notice, unpaid rent |
| 3. Issue & document discovery | Mold mentioned → habitability defense surfaced; notice type confirmed |
| 4. Related issue surfacing | Household of 3 → ILRPP eligibility; kids mentioned → child support enforcement |
| 5. Guided next steps | Appearance deadline added; ILRPP deadline added; document checklist assembled |
| 6. Warm handoff | Not taken in happy path; available (DuPage Legal Aid linked) |
| 7. Re-integration | N/A in happy path; available if handoff taken |
| 8. File or appear | E-file Appearance form with 18th Judicial Circuit |
| 9. Follow-up | Confirmation email; sidebar persists; reminders set; account created at this moment |

See [Happy Path Narrative](./happy-path-jane.md) for the full story and [User Flows Matrix](./user-flows.md) for how Jane's path varies across AI modes and auth states.

---

## Alternate Paths

The nine stages apply to all users. What differs is how each stage is supported.

**Anonymous user** — Same stages, no persistent sidebar. The portable case file (encrypted export) carries stages 5–7 across sessions and devices. The user is responsible for re-importing state if they return on a different device. Account creation is offered at stage 8 or 9, not required earlier.

**Basic / no-AI path** — Stages 2–4 are handled by the user browsing topic pages. The AI's clarifying questions and proactive issue surfacing are not available; the user must identify their own issue and related concerns. Stage 5 requires the user to identify deadlines manually. Stage 8 is download-only; e-filing is not available without integration.

**Warm handoff path** — Stages 6–7 are the critical loop. The user exits to a legal aid intake form or guided interview tool; case context travels with them. The portal resumes at stage 5 or 8 when the user returns, incorporating any new facts or documents from the external tool.

**Mid-flow abandonment & resume** — A user can exit at any stage. Anonymous users resume via the portable case file. Authenticated users resume via the persistent sidebar. The portal never loses state; users do not start over.

**Post-resolution re-entry** — A user returns after a court visit with new information: a continued hearing date, a new order, a filed counterclaim. They re-enter at stage 2 or 3 with their existing case context intact and move through the flow again with updated facts.

---

## Open Questions for Legal Review

These questions apply across all paths and modes. Answers will inform disclosure language, consent flows, and data handling requirements.

1. **Portable case file** — What personally identifiable information is safe to include in an encrypted export file? What consent language is required before the file is created or downloaded?

2. **Warm handoff** — What information can flow to a legal aid organization without creating an attorney-client relationship? What consent is required before case context is transmitted to a third party?

3. **Domestic violence safety** — Which fields must be excluded from any export or handoff, regardless of user consent? Are there additional safety checks required before certain topics are surfaced?

4. **AI-generated content** — What disclaimers are required for AI-generated legal information? Where must "this is not legal advice" appear, and in what form? Are there topic categories that require a mandatory disclaimer regardless of AI mode?

5. **Minor users** — Are there age verification or parental consent requirements if the portal is accessed by a minor navigating a family law matter on their own behalf?

6. **Record retention** — How long can the portal retain conversation history and case facts? What deletion rights does the user have, and how are they communicated?

---

## References

- [Happy Path Narrative](./happy-path-jane.md)
- [User Flows Matrix](./user-flows.md)
- [Demo Flow (Jane)](./demo-flow-jane.md)
- [AI Tone Guide](./ai-tone-guide.md)
