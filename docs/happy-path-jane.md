# Jane's Happy Path — Litigant Portal Narrative

## Purpose

A concrete, end-to-end story of Jane's ideal experience in the Litigant Portal (LP). Full AI, everything works, LP handles everything in-system through e-file resolution. This is the base story — all other matrix variations (Hybrid, Basic, Anon, analog resolution) branch from here.

Jane is a self-represented tenant in Franklin County, Ohio; her matter is in Franklin County Municipal Court (Columbus). The legal specifics below trace to the live eviction corpus (Ohio Revised Code Chapter 1923, ORC 5321, the FCMC clerk FAQ, and LASCO tenant guides).

---

## The Story

### First Load

Jane opens the portal on her phone. She hasn't created an account.

The portal's home screen shows a single, open chat input and a short tagline: _"Describe your legal situation. We'll help you figure out what to do."_ No topic grid, no menus, no forms to fill out yet.

**LP:** "What's going on? You can describe it in your own words."

---

### Jane Describes Her Situation

**Jane:** "I got eviction papers from my landlord."

**LP:** "I'm sorry to hear that. Can you tell me what the papers are? For example, is it a court summons with a hearing date, or a notice from your landlord telling you to leave?"

_LP asks one question at a time. It doesn't ask for her name, her address, or her case number yet._

**Jane:** "It's from the court. There's a hearing date and it says I owe back rent."

**LP:** "Got it. That's an eviction complaint with a Summons in Forcible Entry and Detainer. It has two parts: the first asks the court for possession of your home, and the second asks for money, the back rent your landlord says you owe. The money part matters for a deadline we'll get to. First, has your hearing date already passed, or is it still ahead?"

**Jane:** "It's in about two weeks."

---

### Surfacing the Defense

**LP:** "Good, there's still time to prepare. Can you tell me why there's unpaid rent? Sometimes the reason matters a lot legally."

**Jane:** "I've been deducting repair costs from my rent. There's mold in the bathroom and my landlord won't fix it."

**LP:** "That's important, and Ohio has habitability protections under ORC 5321. But there's a catch worth knowing early: in Ohio, holding back or deducting rent on your own is risky, and bad conditions by themselves usually aren't a defense to unpaid rent. The protected route is to deposit your rent with the court clerk instead of the landlord. Bringing your repair requests and photos to the hearing still matters. If you want a read on whether your specific situation adds up to a defense, legal aid can review it, but let's get you set up either way."

_Sidebar: "Habitability defense — rent escrow + gather repair evidence" is added._

**LP:** "I want to make sure I find everything you might qualify for. Can you tell me how many people are in your household?"

---

### Eligibility Surfacing

**Jane:** "Me and my 2 kids."

**LP:** "A household of 3. There are emergency rental assistance programs that can help cover overdue rent, and income factors in. Legal Aid of Southeast and Central Ohio (LASCO) can help you find what you qualify for and apply. I'm adding that to your action items so it's tied to your hearing timeline."

_Sidebar: rental assistance + contact LASCO added._

---

### Proactive Connection

**LP:** "You mentioned you have two kids. Do you receive child support from their other parent?"

**Jane:** "My ex is supposed to pay but he doesn't consistently."

**LP:** "Unpaid child support can be enforced through your county Child Support Enforcement Agency, and getting that stabilized could reduce the financial pressure behind situations like this. I'm adding child support enforcement resources to your action items."

_Sidebar: Child support enforcement resources added._

---

### Identifying the Filing Requirement

**LP:** "Here's the deadline I mentioned. Because your complaint includes a claim for money, you can file a written Answer to that claim, and it's due within 28 days of the day you were served, even though your hearing usually comes first. Filing an Answer costs nothing. If you miss it, your landlord can ask for a default judgment for the full amount without hearing your side."

_Sidebar: 28-day Answer deadline added._

**LP:** "I can help you prepare that Answer. Do you want to do that now, or do you have a few more questions first?"

**Jane:** "Let's do it now."

---

### Form Preparation

**LP:** "I'll walk you through it. Most of the information I need, I already have from our conversation. Let me confirm a few things."

LP pre-fills what it knows:

- Court: Franklin County Municipal Court
- Case type: Eviction (unpaid rent, with a money claim)
- Tenant name: _[asks]_
- Landlord name: _[asks]_
- Property address: _[asks]_

**LP:** "What's the address of the rental property?"

**Jane:** provides address.

**LP:** "And your landlord's name or property management company?"

**Jane:** provides name.

**LP:** "Last one — your full legal name as it should appear on the filing."

**Jane:** provides name.

_LP assembles the Answer. Jane sees a preview on screen._

**LP:** "Here's your completed Answer for Franklin County Municipal Court. Review it — if anything looks wrong, tell me and we'll fix it."

Jane reviews. Everything looks correct.

---

### Court Plan Assembly

**LP:** "Along with the Answer, here's your court plan."

**Court Plan — Jane Martin, Franklin County Eviction**

- **Court location:** Franklin County Municipal Court, 375 South High Street, Columbus, OH 43215. The Self Help Center is on the 16th floor. Arrive early and check in with the bailiff.
- **What to bring:** Lease agreement, proof of repair requests (texts, emails), receipts for any payments, photos of the mold, proof of any rent you deposited with the clerk.
- **Key dates:**
  - Answer to the money claim: due within 28 days of service
  - Hearing date: [from your summons]
- **Next steps:**
  1. File your Answer (we'll do this now)
  2. Apply for emergency rental assistance (link + in your action items)
  3. Contact child support enforcement (resource link added)
  4. Gather the documents listed above before your hearing
- **Resources:**
  - Legal Aid of Southeast and Central Ohio (LASCO)
  - Franklin County Municipal Court Self Help Center (16th floor)
  - Ohio Revised Code Chapter 1923 (eviction law)
  - County Child Support Enforcement Agency (CSEA)

---

### Resolution — E-File

**LP:** "Your Answer is ready to file. You have a few options:"

1. **File it now** — LP submits it to Franklin County Municipal Court (requires you to create an account so the court can confirm receipt)
2. **Download and file in person** — PDF download, bring to the clerk's office at 375 South High Street
3. **Email or print** — receive a copy to handle yourself

**Jane:** "File it now."

**LP:** "To file, I need to verify your identity. This takes about 2 minutes. Create a free account and we'll submit on your behalf."

Jane creates an account. LP files the Answer with Franklin County Municipal Court.

**LP:** "Filed. You'll receive a confirmation by email. Your case summary, deadlines, and next steps are saved to your account — you can access them any time."

_Jane is now logged in. The sidebar is persistent. Reminders are set for deadlines._

---

## Key LP Touchpoints

| Moment               | What LP Does                                                      |
| -------------------- | ----------------------------------------------------------------- |
| First load           | Open chat, no friction                                            |
| Issue identification | One question at a time, natural language                          |
| Defense surfacing    | Habitability angle + Ohio rent-escrow route surfaced from context |
| Eligibility          | Rental assistance surfaced, routed to LASCO                       |
| Proactive connection | Child support raised without Jane asking                          |
| Filing requirement   | 28-day Answer deadline flagged before Jane asks                   |
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

- [Demo Flow (Jane)](./demo-flow-jane.md) — 8-step demo flow (abbreviated version)
- [User Flows Matrix](./user-flows.md) — 3×2 matrix mapping all variations
- [AI Tone Guide](./ai-tone-guide.md) — How LP communicates
- [Expert Feedback](./expert-feedback/2026-01-15-lawyer-eviction.md) — Lawyer review of eviction flow
