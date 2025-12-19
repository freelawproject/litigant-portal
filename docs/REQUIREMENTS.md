# Litigant Portal - Product Requirements

## Target Users

Self-represented litigants facing barriers to justice (financial, time, mobility constraints).

**Mobile-first** - Many users access exclusively via smartphone, often older devices.

---

## MVP Scope

### Core Systems

- User authentication + save/resume
- Guided form-filling with external tool integration (A2J Author, HotDocs, DocAssemble)
- Plain-language case type, document type, party role selection
- Court → portal → user notifications (email/SMS)
- Case search and attachment to existing cases
- Case history view
- Mobile-responsive design
- WCAG accessibility compliance

### Supporting Features

- Legal information by case type
- Courthouse locations (Google Maps integration)
- Courtroom preparation guidance
- Dynamic homepage with case-specific content

---

## Post-MVP

1. **AI Search/Chat** - Resource discovery based on legal issue description
2. **Smartphone Camera Scanning** - 300 DPI/OCR document capture
3. **E-Filing Integration** - Court system integration (varies by court)
4. **Payment Processing** - Credit card/ACH with fee waiver logic

---

## UX Principles

**Design Philosophy:** Users are stressed, unfamiliar with legal processes, limited time/tech literacy. Every interaction must reduce cognitive load.

**Guiding Standard:** "Can someone with one usable hand navigate this?" An accessible app is easier for everyone.

### Key Patterns

| Pattern                 | Implementation                                                         |
| ----------------------- | ---------------------------------------------------------------------- |
| **Document Scanning**   | Bank check deposit UX - edge detection, auto-capture, quality feedback |
| **Case Type Selection** | Decision tree, not dropdown - plain language questions                 |
| **Form Filling**        | One question per screen, progress indicator, auto-save                 |
| **Payment**             | Apple/Google Pay, fee waiver check first, one-tap pay                  |
| **Dashboard**           | To-do list with status indicators, action buttons                      |
| **Errors**              | Human language ("Payment didn't go through") not codes                 |
| **Document Status**     | Package tracking pattern with push notifications                       |

---

## Success Metrics

| Metric                 | Target                 |
| ---------------------- | ---------------------- |
| Time to first filing   | < 15 min (simple case) |
| Mobile completion rate | ≥ desktop              |
| Abandonment rate       | Track per step         |
| Help contact rate      | Lower = better UX      |
