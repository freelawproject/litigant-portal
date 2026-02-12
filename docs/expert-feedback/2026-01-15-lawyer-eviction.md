# Lawyer Review: Jane Eviction Flow

**Date:** 2026-01-15
**Reviewer:** Lawyer (name TBD)
**Scenario:** Jane's eviction demo flow

---

## Raw Feedback (Verbatim)

> 1. Knows county = DuPage b/c of IP address?
> 2. Should ask what the papers are. There are different types of evictions. Court paperwork should say.
> 3. Why is she being evicted? (Paying for repairs, so thinks she doesn't need to pay rent equal to that? Didn't pay rent b/c she didn't have the money that month b/c of some other life event?) The no. 2 question about what the papers are could clarify no. 3
> 4. I don't like the specific phrasing with the "like child support?" part. That feels like an awkward way to ask the question. Maybe "You mentioned that you have 2 children. Do you receive child support from their other parent?"
> 5. She likely needs to file an answer to the eviction notice. Perhaps she just needs to appear in court on court date, but may need to file something beforehand. I think it depends on the type of eviction. But idk. I'd have to do some legal research (not time today to do that)
>
> Like the sidebar

---

## Lessons Extracted

| Category             | Lesson                                                                               | Applies To                         |
| -------------------- | ------------------------------------------------------------------------------------ | ---------------------------------- |
| **Legal accuracy**   | Different eviction types exist - ask what papers say                                 | Any case with multiple variants    |
| **Legal accuracy**   | Filing requirements vary by case type - research needed                              | All case types                     |
| **Tone/UX**          | Don't lead with specific examples ("like child support?") - feels awkward            | All follow-up questions            |
| **Tone/UX**          | Reference what user already said ("You mentioned...") before asking related question | All contextual questions           |
| **Tone/UX**          | Let paperwork do the explaining when possible ("papers should say")                  | Any case involving court documents |
| **Information flow** | Questions can answer multiple things (paper type clarifies reason)                   | Question sequencing                |

---

## Changes Made

Based on this feedback, we updated:

1. **AI Tone Guide** (`docs/ai-tone-guide.md`)

   - Added "Don't Lead with Examples" anti-pattern
   - Added "Reference What They've Said" guidance
   - Added "Let Paperwork Do the Work" approach

2. **Demo Flow** (`docs/demo-flow-jane.md`)
   - Step 1: Show county detection ("detected from your location")
   - Step 2: Ask ONE question about paper type first
   - Step 2b: Follow up naturally based on answer
   - Step 5: Rephrased child support question
   - Step 6: Added filing requirements (appearance deadline)

---

## Open Research Items

- [ ] Filing requirements by eviction type in IL (5-day, 10-day, 30-day)
- [ ] Deadline for filing appearance in DuPage County
- [ ] Rent withholding rules in Illinois (habitability defense)

---

## References

- [Demo Flow](../demo-flow-jane.md)
- [AI Tone Guide](../ai-tone-guide.md)
