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
