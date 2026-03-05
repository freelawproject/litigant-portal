# User Flows

This document maps the two primary auth states across the full AI support spectrum. It is the canonical reference for product and engineering decisions about what the portal does and when.

---

## Jane's Journey — 3×2 Matrix

Rows = Jane's 8 steps + Resolve. Columns = 3 AI modes × 2 auth states. Cells are concise UX descriptions; differences between auth states are the primary signal.

| Step                           | Full AI · Anon                                                                        | Full AI · Auth                                                | Hybrid · Anon                                                     | Hybrid · Auth                     | Basic · Anon                                  | Basic · Auth                    |
| ------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------- | --------------------------------------------- | ------------------------------- |
| **1. Arrive**                  | County auto-detected; chat opens; no sidebar                                          | County from profile or auto-detected; sidebar visible (empty) | County selector + topic picker                                    | County from profile; topic picker | Topic grid; county selector                   | Topic grid; county from profile |
| **2. "I got eviction papers"** | Free-text chat; AI classifies issue                                                   | Same + issue type saved to case                               | Select issue type from guided menu                                | Same + saved to case              | Navigate to Housing → Eviction info           | Same + saved to history         |
| **2b. "It says 5-day notice"** | AI asks "What does it say at the top?"; user answers freely                           | Same + notice type added to sidebar                           | Dropdown: "What type of notice?"                                  | Same + saved to case              | Read info article on notice types             | Same                            |
| **3. Mold / habitability**     | Free text; AI identifies habitability defense                                         | Same + "Habitability defense" added to sidebar                | Structured intake: reason for non-payment → AI flags habitability | Same + saved to case              | User reads habitability info; self-identifies | Same                            |
| **4. Household of 3**          | AI asks naturally; surfaces ILRPP eligibility                                         | Same + ILRPP deadline added to sidebar                        | Form field: household size → eligibility check shown              | Same + saved to case              | User self-identifies from info page           | Same                            |
| **5. Child support**           | AI proactively surfaces enforcement resources                                         | Same + resources added to sidebar                             | Not proactively surfaced; available via topic browse              | Same                              | Not surfaced; user must find via topic browse | Same                            |
| **6. Appearance deadline**     | AI identifies filing requirement; sidebar updated (ephemeral)                         | Same + saved to DB; reminder possible                         | AI tool calculates deadline from notice date; shown in UI         | Same + saved; reminder possible   | User must find on court website               | Same; no automated deadline     |
| **7. Court prep**              | AI provides courthouse logistics and document checklist                               | Same + checklist saved to sidebar                             | Court info card: address, parking, what to bring                  | Same + saved checklist            | User navigates to courthouse info page        | Same                            |
| **Resolve**                    | Export encrypted case file; download / email / print forms; warm handoff to legal aid | Same + e-file; case persisted; share with legal aid attorney  | Download completed forms; export / print                          | Same + e-file; case persisted     | Download blank forms; print; bring to court   | Same + saved history            |

### Key patterns to plan and test

- **Proactive connection of related issues (steps 4–5) is a Full AI feature, not a gap.** The AI surfacing child support when Jane mentions her kids — without her asking — is core value of the Full AI path. Hybrid and Basic users get this only if they navigate to it themselves. Test: does the AI reliably make these connections? What related issues should it always check for given a case type?
- **Encrypted export includes a deadline/todo list.** The portable case file carries not just the chat transcript and extracted document data, but a structured event list: filing deadlines, required appearances, application deadlines, action items. This is the anonymous user's equivalent of the sidebar. Format should be importable by calendar apps (iCal/ICS) as well as readable in the portal on re-upload.
- **Sidebar = living document (auth) vs. point-in-time export (anon).** For logged-in users the sidebar is a persistent, updateable record — deadlines get checked off, new items added as the case progresses. For anonymous users the export is a snapshot: accurate at time of export, not updated automatically. UX should make this distinction clear ("Your case summary as of [date]").
- **Anon and Auth are intentionally parallel at MVP.** The logged-in experience is not meaningfully richer during Triage and Prepare. Auth benefits (persistence, reminders, e-file, case sharing) surface at Resolve and after. The prompt to create an account belongs at that moment — not at arrival.
- **Appearance deadline (step 6):** Full AI and Hybrid both surface this; Basic does not. A missed appearance is a default judgment. Consider whether Basic should at minimum link to court rules.
- **Resolve options diverge sharply:** E-filing is Auth-only. Warm handoff to legal aid is available to all but works differently per mode. Anonymous users depend on the portable case file to carry anything out of the session.

## The Spectrum

The portal is designed to work at three levels of AI support. **AI is MVP-scope** — Nathan's AI team is building the agentic tooling in parallel with this front/back-end work. The spectrum exists because courts may opt out of AI, AI may be unavailable, and some users may prefer not to use it. The architecture must support graceful degradation from Full AI → Hybrid → Basic.

| Mode        | Description                                                                                                                                                                   | Analogy                                        |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Full AI** | Conversational end-to-end. AI drives triage, extracts facts from documents, populates the case file, and drafts responses. Current demo (Jane's journey).                     | A knowledgeable friend who happens to know law |
| **Hybrid**  | AI runs as agentic tools on the backend (issue classifier, deadline calculator, form pre-fill from transcript). Frontend is discrete: information cards, form wizard, e-file. | Smart court kiosk                              |
| **Basic**   | No AI. Browse topics, search courthouse info, fill forms manually, e-file or download.                                                                                        | Current court self-help website                |

---

## Flow Stages

All flows move through three stages:

1. **Triage** — What's my situation and what do I need?
2. **Prepare** — Gather facts, fill forms, understand deadlines
3. **Resolve** — E-file, download forms, hand off to legal aid, show up to court

---

## Anonymous User Flow

Anonymous users have full access to core functionality. Login is never a gate — it is an upgrade for continuity.

### Triage

| Mode    | Experience                                                                                                                               |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Full AI | Chat-first. User describes situation in natural language. AI classifies the legal issue, identifies county, asks one question at a time. |
| Hybrid  | Topic selection → AI recommends relevant information cards and applicable forms.                                                         |
| Basic   | Browse topic grid → read information cards for selected legal area.                                                                      |

### Prepare

| Mode    | Experience                                                                                                                                                                                                 |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Full AI | Chat gathers context (household size, notice type, income bracket, etc.). User uploads documents; AI extracts structured data and populates the case file live. Sidebar tracks deadlines and action items. |
| Hybrid  | User uploads documents → AI pre-fills form fields → user confirms each field. Guided wizard handles fields without uploaded source.                                                                        |
| Basic   | User selects a form → step-by-step guided wizard, one question per screen, no AI assist.                                                                                                                   |

### Resolve

| Mode    | Experience                                                                         |
| ------- | ---------------------------------------------------------------------------------- |
| Full AI | Export case file → e-file, download completed forms, or warm handoff to legal aid. |
| Hybrid  | E-file OR export completed forms → download / email / SMS / print.                 |
| Basic   | Download blank form → print → bring to court.                                      |

---

## Authenticated User Flow

Authenticated users get all anonymous capabilities plus persistence. The sidebar, case history, and deadline tracking are backed by the database rather than browser session.

### What login adds

| Anonymous                        | Authenticated                                      |
| -------------------------------- | -------------------------------------------------- |
| Full chat, upload, extract       | All anonymous features                             |
| Export/import portable case file | Persistent case history — resume without uploading |
| Download/print/email/SMS forms   | Saved deadlines and action items in sidebar        |
| Warm handoff to legal aid        | Legal aid attorney can access shared case          |
|                                  | Court notifications (email/SMS pushed from court)  |
|                                  | E-filing identity verification                     |

At MVP, triage and prepare are intentionally parallel — the logged-in experience is not meaningfully richer during those stages. Auth benefits surface at Resolve and after. The prompt to create an account belongs at that moment, not at arrival. Additional logged-in benefits will layer in over time.

---

## Portable Case File (Anonymous Continuity)

The portable case file is the anonymous user's save state. It replaces persistent login for users who cannot or will not create an account.

### Contents

A single encrypted JSON file containing:

- Chat transcript (messages array)
- Extracted document data (`CourtDocumentData` from PDF upload)
- **Deadline and todo list** — structured event list of all filing deadlines, required appearances, application windows, and action items surfaced during the session. Exportable as ICS/iCal for calendar import.
- County and court information
- User-provided facts (household size, income bracket, notice type, etc.)
- Schema version (for forward compatibility on import)
- Export timestamp (displayed on re-import as "Your case summary as of [date]")

The deadline/todo list is the anonymous user's equivalent of the authenticated sidebar. It is a **point-in-time snapshot** — accurate at export, not updated automatically. The UX must make this clear.

The authenticated sidebar is a **living document** — deadlines get checked off, new items added as the case progresses, reminders sent as dates approach.

### Export

- "Save my progress" button always visible
- Soft prompt before navigating away
- Prompt after completing each stage (natural save points)

### Import

- Upload file on any device → session state restored
- Works across browsers, devices, incognito windows
- No account required

### Security

Encryption: AES-256-GCM with key derived from a user-chosen passphrase via PBKDF2/Argon2, implemented entirely in the browser via the Web Crypto API.

**The portal never sees the key.** No server compromise can expose the file contents.

File format:

```json
{ "version": 1, "iv": "<base64>", "ciphertext": "<base64>" }
```

**Passphrase recovery is impossible.** The UX must be explicit: _"Write this down. We cannot recover it."_

Filename: `case-XXXXXX.enc` — no name, no date, no case type in the filename.

### DV Safety Principle

> "If this file is found on my phone by my abuser, it must not identify me or reveal my legal situation."

Implications:

- No PII in filename
- No PII readable without passphrase
- **Safe export option**: strips name and contact fields entirely — exports legal facts only
- Passphrase guidance: avoid memorable personal phrases; suggest random word combinations

⚠️ **Legal review required before implementing:**

- What PII is safe to include in an encrypted portable file?
- Consent language for exporting and sharing

---

## Warm Handoff to Legal Aid

A warm handoff lets a user share their case with a legal aid attorney or self-help center staff in one action.

### Options (to be determined with legal)

| Method                        | Description                                                     | Privacy tradeoff                                      |
| ----------------------------- | --------------------------------------------------------------- | ----------------------------------------------------- |
| Email/SMS with encrypted file | User sends their own case file to a legal aid intake address    | User controls; legal aid needs passphrase             |
| Portal-mediated share link    | Time-limited read-only link; portal re-encrypts for recipient   | Portal can read the file during share window          |
| Print summary                 | Sanitized one-page PDF safe to hand to a self-help center clerk | No digital transmission; user chooses what to include |

⚠️ **Legal review required before implementing:**

- What information can flow from user to legal aid without creating a formal attorney-client relationship?
- Consent requirements for portal-mediated sharing
- Attorney-client privilege: does sharing a case file create a relationship?

---

## Resolve Options

| Option                             | Anonymous             | Authenticated       | Notes                                    |
| ---------------------------------- | --------------------- | ------------------- | ---------------------------------------- |
| E-file                             | TBD — court-dependent | Yes                 | Requires identity verification per court |
| Download completed forms (PDF)     | Yes                   | Yes                 | Pre-filled from case file or form wizard |
| Email forms to self                | Yes (one-time)        | Yes (saved address) |                                          |
| SMS forms                          | Yes                   | Yes                 |                                          |
| Print                              | Yes                   | Yes                 |                                          |
| Warm handoff to legal aid          | Yes                   | Yes                 | See section above                        |
| Guided interview (A2J/DocAssemble) | Yes                   | Yes                 | External tool integration — post-MVP     |

---

## Open Questions

Items flagged for future work or legal input:

1. **Case model** — No `Case` DB model exists yet. Authenticated flow (persistent sidebar, history, deadlines) requires one. Design needed before implementation.
2. **E-filing** — Court-dependent. Requires per-court integration research. Anonymous e-filing rules vary.
3. **Portable file encryption** — Implementation spec confirmed (client-side PBKDF2/AES-GCM), but DV safety language and consent copy require legal review before shipping.
4. **Warm handoff mechanism** — Three options identified; selection requires legal review on privilege and consent.
5. **Guided interviews** — A2J Author / DocAssemble integration; post-MVP scope.
6. **REQUIREMENTS.md** — Needs updating to reflect AI as MVP-scope (currently listed as Post-MVP item 1).

---

## References

- [Happy Path Narrative](./happy-path-jane.md) — Full AI · Auth story in full detail (base for all variations)
- [Demo Flow (Jane)](./demo-flow-jane.md) — 8-step ITC demo flow (abbreviated)
- [Requirements](./REQUIREMENTS.md) — MVP/post-MVP scope (AI section needs updating)
- [Architecture](./ARCHITECTURE.md) — Tech stack and component structure
- [AI Tone Guide](./ai-tone-guide.md) — How the AI communicates
- [Expert Feedback](./expert-feedback/2026-01-15-lawyer-eviction.md) — Lawyer review of demo flow
