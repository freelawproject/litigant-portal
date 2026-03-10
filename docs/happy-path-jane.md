# Jane's Happy Path — Litigant Portal Narrative

## Purpose

A concrete, end-to-end story of Jane's ideal experience in the Litigant Portal (LP). Full AI, everything works, LP handles everything in-system through e-file resolution. This is the base story — all other matrix variations (Hybrid, Basic, Anon, analog resolution) branch from here.

---

## The Story

### First Load

Jane opens the portal on her phone. She hasn't created an account.

The portal's home screen shows a single, open chat input and a short tagline: _"Describe your legal situation. We'll help you figure out what to do."_ No topic grid, no menus, no forms to fill out yet.

**LP:** "What's going on? You can describe it in your own words."

---

### Jane Describes Her Situation

**Jane:** "I got eviction papers from my landlord."

**LP:** "I'm sorry to hear that. Can you tell me — what does the notice say at the top? Something like '5-day notice' or '30-day notice'?"

_LP asks one question at a time. It doesn't ask for her name, her address, or her case number yet._

**Jane:** "It says 5-day notice to pay or quit."

**LP:** "Got it. A 5-day notice means your landlord is claiming you owe unpaid rent, and they're giving you 5 days to pay before they can file for eviction in court. Has a court date been set yet, or is this the first paper you've received?"

**Jane:** "Just this paper so far."

---

### Surfacing the Defense

**LP:** "Understood — you're in the early stage, which means there's still time to act. Can you tell me why there's unpaid rent? Sometimes the reason matters a lot legally."

**Jane:** "I've been deducting repair costs from my rent. There's mold in the bathroom and my landlord won't fix it."

**LP:** "That's important. Illinois has habitability protections — landlords are required to maintain safe and livable conditions. Because you withheld rent due to a repair issue, you may have a habitability defense that could affect how a court views your case."

_Sidebar: "Habitability defense — research" is added._

**LP:** "I want to make sure I find everything you might qualify for. Can you tell me how many people are in your household?"

---

### Eligibility Surfacing

**Jane:** "Me and my 2 kids."

**LP:** "A household of 3. Based on that, you may qualify for the Illinois Rental Payment Program (ILRPP), which can help cover overdue rent. Income also factors in — roughly, is your household income under $60,000 a year?"

**Jane:** "Yeah, around $50,000."

**LP:** "You're likely eligible. I'm adding the ILRPP application to your action items — there's a deadline tied to your court date, so we'll make sure you don't miss it."

_Sidebar: ILRPP application + deadline added._

---

### Proactive Connection

**LP:** "You mentioned you have two kids. Do you receive child support from their other parent?"

**Jane:** "My ex is supposed to pay but he doesn't consistently."

**LP:** "Unpaid child support can be enforced through the state — getting that stabilized could reduce the financial pressure behind situations like this. I'm adding child support enforcement resources to your action items."

_Sidebar: Child support enforcement resources added._

---

### Identifying the Filing Requirement

**LP:** "Here's something critical for a 5-day notice case in DuPage County: before your court date, you'll need to file a written 'appearance' — a document that tells the court you plan to contest the eviction. Missing this can result in a default judgment against you."

_Sidebar: Appearance filing deadline added._

**LP:** "I can help you prepare that document. Do you want to do that now, or do you have a few more questions first?"

**Jane:** "Let's do it now."

---

### Form Preparation

**LP:** "I'll walk you through it. Most of the information I need, I already have from our conversation. Let me confirm a few things."

LP pre-fills what it knows:

- County: DuPage
- Court: 18th Judicial Circuit
- Case type: Eviction (5-day notice, unpaid rent)
- Tenant name: _[asks]_
- Landlord name: _[asks]_
- Property address: _[asks]_

**LP:** "What's the address of the rental property?"

**Jane:** provides address.

**LP:** "And your landlord's name or property management company?"

**Jane:** provides name.

**LP:** "Last one — your full legal name as it should appear on the filing."

**Jane:** provides name.

_LP assembles the Appearance form. Jane sees a preview on screen._

**LP:** "Here's your completed Appearance form for the 18th Judicial Circuit. Review it — if anything looks wrong, tell me and we'll fix it."

Jane reviews. Everything looks correct.

---

### Court Plan Assembly

**LP:** "Along with the form, here's your court plan."

**Court Plan — Jane Martin, DuPage County Eviction**

- **Court location:** 18th Judicial Circuit Court, 505 N. County Farm Rd, Wheaton IL 60187. Parking: County Farm Rd lot, free. Arrive 30 min early for security.
- **What to bring:** Lease agreement, proof of repair requests (texts, emails), receipts for any payments, photos of the mold, ILRPP application confirmation if you've applied.
- **Key dates:**
  - Appearance filing deadline: [calculated from notice date]
  - ILRPP application deadline: [tied to court date]
  - Court date: [if known, or "check your notice"]
- **Next steps:**
  1. File your Appearance (we'll do this now)
  2. Apply for ILRPP assistance (link + deadline in your action items)
  3. Contact child support enforcement (resource link added)
  4. Gather documents listed above before your court date
- **Resources:**
  - DuPage County Legal Aid
  - Illinois ILRPP program
  - 18th Judicial Circuit self-help center (location + hours)
  - Child Support Services (Illinois DCSS)

---

### Resolution — E-File

**LP:** "Your Appearance is ready to file. You have a few options:"

1. **File it now** — LP submits directly to the 18th Judicial Circuit (requires you to create an account so the court can confirm receipt)
2. **Download and file in person** — PDF download, bring to the clerk's office
3. **Email or print** — receive a copy to handle yourself

**Jane:** "File it now."

**LP:** "To e-file, I need to verify your identity. This takes about 2 minutes. Create a free account and we'll submit on your behalf."

Jane creates an account. LP files the Appearance with the 18th Judicial Circuit e-filing system.

**LP:** "Filed. You'll receive a confirmation by email. Your case summary, deadlines, and next steps are saved to your account — you can access them any time."

_Jane is now logged in. The sidebar is persistent. Reminders are set for deadlines._

---

## Key LP Touchpoints

| Moment               | What LP Does                                                      |
| -------------------- | ----------------------------------------------------------------- |
| First load           | Open chat, no friction                                            |
| Issue identification | One question at a time, natural language                          |
| Defense surfacing    | Habitability defense identified from context                      |
| Eligibility          | ILRPP surfaced proactively from household size                    |
| Proactive connection | Child support raised without Jane asking                          |
| Filing requirement   | Appearance deadline flagged before Jane asks                      |
| Form prep            | Pre-filled from context, minimal additional input                 |
| Court plan           | Assembled from case facts — location, dates, checklist, resources |
| Resolution           | E-file in-portal, account created at the last moment (not a gate) |
| Post-resolution      | Persistent sidebar, deadline reminders, case history              |

---

## What This Story Is Not

- Not legal advice — LP provides information and helps Jane understand her options
- Not a guarantee of outcome — LP helps Jane be as prepared as possible
- Not auth-gated — account creation happens at the natural moment (e-file), not at arrival

---

## Variations to Branch From Here

1. **Anon resolution** — Jane doesn't create an account; downloads form + court plan as PDF/SMS/email
2. **Hybrid path** — Same story, but LP uses structured intake (topic picker, guided wizard) instead of free-text chat
3. **Basic path** — No AI; Jane navigates topic pages, fills forms manually, downloads
4. **Warm handoff** — LP connects Jane to legal aid instead of e-filing
5. **Tech handoff** — Court has its own e-file API; LP passes form data to court system directly
6. **Mid-flow abandonment** — Jane saves progress and returns later (anon: encrypted export; auth: sidebar persists)

---

## References

- [Demo Flow (Jane)](./demo-flow-jane.md) — 8-step ITC demo flow (abbreviated version)
- [User Flows Matrix](./user-flows.md) — 3×2 matrix mapping all variations
- [AI Tone Guide](./ai-tone-guide.md) — How LP communicates
- [Expert Feedback](./expert-feedback/2026-01-15-lawyer-eviction.md) — Lawyer review of eviction flow
