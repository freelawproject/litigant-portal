# Jane's Journey - Demo Flow

**Jane Martin**: Single mom (2 kids, ages 6 & 8), ~$50k income, Franklin County OH, facing eviction.

Abbreviated version of the [happy-path narrative](./happy-path-jane.md). Legal specifics trace to the live eviction corpus (ORC Chapter 1923, ORC 5321, the FCMC clerk FAQ, LASCO guides).

---

## The Flow

### Step 1: Jane Arrives

**Jane:** Opens the portal on her phone.

**AI/UI:** A single open chat input: _"Describe your legal situation. We'll help you figure out what to do."_ No account, no forms, no topic grid.

_No friction - one open door_

---

### Step 2: "I got eviction papers"

**Jane:** "I got eviction papers"

**AI:** "I'm sorry to hear that. Can you tell me what the papers are - a court summons with a hearing date, or a notice from your landlord telling you to leave?"

_One question at a time - doesn't overwhelm_

---

### Step 2b: Jane answers about the papers

**Jane:** "It's from the court - there's a hearing date and it says I owe back rent"

**AI:** "That's an eviction complaint with a summons. It has two parts: one asks the court for possession of your home, the other asks for the back rent. The money part carries its own deadline, which I'll flag. Can you tell me why they say you owe rent? Sometimes the reason matters."

_Confirms understanding, lets the paperwork do the work_

---

### Step 3: Jane explains her situation

**Jane:** "I've been paying for repairs the landlord won't fix - mold in the bathroom - so I deducted it from rent"

**AI:** "Ohio has habitability protections (ORC 5321), but there's a catch worth knowing: holding back or deducting rent on your own is risky, and bad conditions alone usually aren't a defense to unpaid rent. The protected route is depositing your rent with the court clerk. Bring your repair requests and photos to the hearing, and if you want a read on whether it's a defense in your case, legal aid can review it. Before we go on, how many people are in your household?"

- **Sidebar:** Adds "Habitability defense - rent escrow + gather evidence"

_Answers directly, flags the real Ohio rule, transitions naturally_

---

### Step 4: Context gathering

**Jane:** "It's me and my 2 kids"

**AI:** "A household of 3. There are emergency rental assistance programs that can help cover overdue rent. I'm adding that to your action items, tied to your hearing timeline, with how to apply."

- **Sidebar:** Adds rental assistance

_Surfaces help she didn't know about_

---

### Step 5: Child support

**AI:** "You mentioned you have 2 children. Do you receive child support from their other parent?"

**Jane:** "My ex is supposed to pay but doesn't consistently"

**AI:** "Unpaid child support can be enforced through your county Child Support Enforcement Agency, and getting that stabilized could ease the pressure behind situations like this. I'm adding those resources."

- **Sidebar:** Adds child support enforcement resources

_Connects the dots for her_

---

### Step 6: The filing deadline

**AI:** "Because your complaint includes a money claim, you can file a written Answer to it, due within 28 days of the day you were served. Filing it costs nothing, and missing it lets your landlord get a default judgment for the full amount. I'm adding this deadline to your action items."

- **Sidebar:** Adds 28-day Answer deadline

_Flags the critical step she might miss_

---

### Step 7: Court prep

**Jane:** "What should I bring to court?"

**AI:** Provides Franklin County Municipal Court logistics:

- 375 South High Street, Columbus; Self Help Center on the 16th floor
- Arrive early and check in with the bailiff
- Documents to bring: lease, repair requests, payment history, photos of the mold

- **Sidebar:** Adds court prep checklist

---

### Step 8: What happens after

**Jane:** "What happens after?"

**AI:** Explains the hearing, the written Judgment Entry, and next steps - including that if the judge rules for the landlord, a set out can follow a Writ of Restitution within 10 days.

- **Sidebar:** Adds post-court next steps

---

## The Magic Moments

- AI **asks one question at a time** (doesn't overwhelm)
- AI **references what Jane said** ("You mentioned you have 2 children...")
- AI **lets the paperwork do the work** ("What do the papers say?")
- AI **answers directly** - explains the Ohio process instead of sending her to "see a lawyer"
- AI **proactively connects** child support to eviction (holistic help)
- AI **surfaces help** Jane didn't know about (rental assistance)
- AI **flags deadlines** she might miss (the 28-day Answer)
- AI **provides practical details** she couldn't easily find (where to file, what to bring)
- Sidebar **tracks everything** so nothing falls through the cracks

---

## Key Constraint

All information, no legal advice (UPL compliance). LP solves directly where it can; it escalates to legal aid only when it genuinely can't help (case-specific legal judgment) or the issue is serious (e.g. an illegal lockout).

---

## Reference

- [User Story #26](https://github.com/freelawproject/litigant-portal/issues/26)
- [Happy Path (Jane)](./happy-path-jane.md) - full end-to-end narrative
- [AI Tone Guide](./ai-tone-guide.md)
- [Lawyer Feedback](./expert-feedback/2026-01-15-lawyer-eviction.md)
