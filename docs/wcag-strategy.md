# WCAG Accessibility Strategy

_Researched 2026-02-19 · Targeting WCAG 2.2 (published Oct 2023)_

## Compliance target

**WCAG 2.2 Level AA: hard requirement.** Every page, every component, every release. Aligns with DOJ Title II (April 2024) and is the legal standard.

**Selective WCAG 2.2 Level AAA: adopted where they directly serve our users.** Full AAA across an entire site is impractical — W3C itself advises against requiring it as general policy. Instead we adopt specific AAA criteria that matter most for self-represented litigants.

### AAA criteria we adopt

| Criterion | Name                      | Why                                                                   |
| --------- | ------------------------- | --------------------------------------------------------------------- |
| 1.4.6     | Enhanced contrast (7:1)   | Users on cheap screens, bright courthouses, stress-impaired focus     |
| 1.4.8     | Visual presentation       | No justified text, line spacing ≥ 1.5, user-customizable text display |
| 2.2.3     | No timing                 | Legal information shouldn't expire mid-read                           |
| 2.4.9     | Link purpose (link alone) | Every link makes sense without surrounding context                    |
| 2.4.10    | Section headings          | Clear document structure for screen readers and scanning              |
| 3.1.3     | Unusual words             | Legal terms need plain-language definitions                           |
| 3.1.4     | Abbreviations             | Spell out abbreviations on first use                                  |
| 3.1.5     | Reading level             | Content readable at lower secondary level where possible              |

## Testing strategy

Automated tools catch ~30–40% of WCAG issues. The rest requires human judgment.

### Layer 1: Automated (every PR)

- **axe-core** via CI (e.g. `pa11y-ci` or `playwright` + `@axe-core/playwright`) — catches structural ARIA errors, missing alt text, contrast violations, landmark issues
- **Lighthouse CI** — accessibility score regression tracking
- Fail the build on new violations

### Layer 2: Manual (every feature)

- Keyboard-only walkthrough (Tab, Enter, Space, Escape, Arrows)
- Screen reader testing (VoiceOver on Mac; NVDA on Windows in CI if feasible)
- Zoom to 200% — layout shouldn't break
- Color-only information check

### Layer 3: Audit (quarterly or before major releases)

- Full WCAG 2.2 AA checklist review using [WAVE](https://wave.webaim.org/), [axe DevTools](https://www.deque.com/axe/devtools/), and manual testing
- Document findings, track regressions
- Consider professional audit for launch

## WCAG 3.0 future-proofing

There won't be a WCAG 2.3 — the next version is **WCAG 3.0**, a complete rethinking of the standard:

- Replaces pass/fail with a **scoring model** (bronze/silver/gold)
- 174 outcome-based criteria instead of success criteria
- Draft published Sept 2025; W3C Recommendation **not before 2028, likely 2030**
- WCAG 2.2 will not be deprecated for years after 3.0 finalizes

**Our approach:** Build on 2.2 AA now. Good 2.2 practices (semantic HTML, ARIA, keyboard nav, contrast, testing) transfer directly to 3.0. Monitor W3C working drafts annually; reassess when 3.0 reaches Candidate Recommendation.

## Guiding principles

1. **Accessibility is a feature, not a fix.** Built in from the start, not bolted on before launch.
2. **AA is the floor, not the ceiling.** Meet AA everywhere; exceed it where our users benefit.
3. **Test like our users.** Keyboard, screen reader, zoom, low-end devices — not just automated scans.
4. **Automate the automatable.** CI catches regressions; humans catch meaning.
5. **Plain language is accessibility.** Legal jargon is a barrier. Define terms, write clearly.
6. **Declare and track.** Public accessibility statement, versioned target, known limitations documented honestly.

## Sources

### WCAG standards

- [WCAG 2.2 Specification](https://www.w3.org/TR/WCAG22/)
- [WCAG 2.1 Specification](https://www.w3.org/TR/WCAG21/)
- [Understanding AAA Conformance](https://www.w3.org/WAI/WCAG2AAA-Conformance)
- [WCAG 3.0 Introduction](https://www.w3.org/WAI/standards-guidelines/wcag/wcag3-intro/)
- [WCAG 3.0 Timeline](https://www.w3.org/WAI/GL/wiki/WCAG_3_Timeline)
- [WCAG 3.0 History](https://www.w3.org/standards/history/wcag-3.0/)

### WCAG 3.0 analysis

- [AbilityNet — What to Expect from WCAG 3.0](https://abilitynet.org.uk/resources/digital-accessibility/what-expect-wcag-30-web-content-accessibility-guidelines)
- [Deque — 174 New Outcomes for WCAG 3.0](https://www.deque.com/blog/w3c-unveils-174-new-outcomes-for-wcag-3-0/)
- [Knowbility — WCAG 3 Update](https://knowbility.org/blog/2025/be-a-digital-ally-wcag-3-update)

### Compliance guidance

- [All Accessible — WCAG 2.2 Complete Guide](https://www.allaccessible.org/blog/wcag-22-complete-guide-2025)
- [Section 508 — Applicability & Conformance](https://www.section508.gov/develop/applicability-conformance/)
- [GOV.UK — Understanding WCAG](https://www.gov.uk/service-manual/helping-people-to-use-your-service/understanding-wcag)
- [UK DWP — WCAG AA and AAA](https://accessibility-manual.dwp.gov.uk/best-practice/wcag-aa-and-aaa)

### Testing tools

- [WAVE Web Accessibility Evaluator](https://wave.webaim.org/)
- [axe DevTools](https://www.deque.com/axe/devtools/)
- [WebAIM Million](https://webaim.org/projects/million/)

### Industry data

- [Accessibility Checker — State of Web Accessibility 2024](https://www.accessibilitychecker.org/research-papers/the-state-of-web-accessibility-in-2024-research-report/)
- [AudioEye — Accessibility Statistics](https://www.audioeye.com/post/accessibility-statistics/)
