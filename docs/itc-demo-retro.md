# ITC Demo Retrospective

Running notes for lessons learned during the ITC Demo build (Jan 2026).

---

## Decisions Made

### 2026-01-15: Demo Architecture

- **Hybrid response system**: Live LLM with cached fallback for reliability
- **Sidebar panel**: Contextual deadlines/next-steps alongside chat (not inline)
- **Profile approach**: County pre-set, personal details gathered through chat
- **Target device**: Laptop/desktop (projected)

### 2026-01-15: Issue Organization

- Created milestone "ITC Demo - Jan 2026" with 13 issues
- Parent issue #27 as umbrella
- New issues: #87 (prompts), #88 (deadline UI), #89 (sidebar), #90 (caching), #91 (rehearsal)

---

## Problems & Solutions

### 2026-01-23: AI responses too generic and formulaic

**Problem:** AI was giving generic advice before understanding the user's situation:

- "Gather evidence and documentation" without knowing what evidence applies
- Listing all possible defenses before asking why they're being evicted
- Hedging language ("can potentially be a defense") instead of confident guidance
- Every response ending with "Would you like to explore..." formula

**Solution:** Updated CHAT_SYSTEM_PROMPT in config/settings.py:

- Added "ASK BEFORE ADVISING" - ask clarifying questions before listing options
- Banned generic advice like "gather evidence" - instead ask what evidence they already have
- Required direct language: "this is a habitability defense" not "this could potentially be"
- Shortened max response length from 3-4 to 2-3 bullets
- Added "SHOW YOUR WORK" section to explain reasoning with their specific details

**Lesson:** The prompt needs explicit anti-patterns with examples. Telling the AI what NOT to do is as important as telling it what to do.

<!-- Template:
### YYYY-MM-DD: Problem title
**Problem:** What went wrong
**Solution:** How we fixed it
**Lesson:** What to do differently next time
-->

---

## What Worked Well

- Breaking the user story into a concrete 7-step demo flow with sidebar updates
- Separating implementation plan from issue grooming plan
- Using existing issue structure (#27 as parent) rather than creating parallel tracking

---

## What To Improve

<!-- Add items as we discover them -->

---

## Tools & Process Notes

<!-- Notes about Claude Code, GitHub workflow, etc. -->

---

## Questions for Retro Discussion

<!-- Park questions here to discuss at the end -->

- How well did the hybrid caching approach work at the conference?
- Did the sidebar concept resonate with the audience?
- What features got the most interest/questions?

---

## References

- [Demo Flow](./demo-flow-jane.md)
- [Implementation Plan](https://github.com/freelawproject/litigant-portal/issues/32)
- [Jane User Story](https://github.com/freelawproject/litigant-portal/issues/26)
- [Milestone](https://github.com/freelawproject/litigant-portal/milestone/1)
