Litigant Portal - Requirements Summary

Target Users
Self-represented litigants facing barriers to justice (financial, time, mobility constraints). **Mobile-first** design is critical—many users will access exclusively via smartphone.

MVP Scope (Must-Have Now)

Core Systems

-   User authentication + save/resume
-   Guided form-filling with external tool integration/linking (A2J Author, HotDocs, DocAssemble)
-   Plain-language case type, document type, and party role selection
-   Court → portal → user notifications (email/SMS)
-   Case search and attachment to existing cases
-   Case history view
-   Mobile-responsive design
-   WCAG accessibility compliance

Supporting Features

-   Legal information by case type
-   Courthouse locations (with Google Maps integration preferred)
-   Courtroom preparation guidance
-   Dynamic homepage with case-specific content
-   Dedicated email & SMS services/capabilities
    Post-MVP Must-Haves

1. **AI Search/Chat Interface** - Contextual resource discovery based on user's legal issue description (requires strong user trust: AI training and AI agent ‘expert’ should verify
2. **Smartphone Camera Scanning** - Document capture meeting 300 DPI/OCR standards via mobile camera

Core E-Filing System (Court by Court specific on level of full integration)

-   E-filing integration with court systems
-   Credit card/ACH payment processing (can have special Vendor rules ex: Tyler)
-   Fee waiver forms with automatic bypass logic (may require judge approval)

Technical Architecture

Guided Interview Strategy

-   Phase 1 (MVP): Integration/linking to external tools (A2J, HotDocs, DocAssemble)
-   Phase 2: Potential unified player consuming all formats (XML, JSON) → outputs for e-filing/intake

Document Standards

-   300 DPI scanned documents (min recommendation for OCR)
-   OCR-searchable PDFs preferred
-   No embedded multimedia/audio/programming

System Design

-   Modular architecture: Portal operates standalone or integrates with existing court management systems
-   EFSP compatibility for attorney filing services (check certification requirements)
-   Role-based access (litigant, clerk, judge, IT)

Critical MVP Success Factors

1. **Mobile-first UX** - Majority of users will access via smartphone
2. **AI Reliability** - Users need to trust the AI responses
3. **Plain language** - Legal jargon translation essential for self-represented users

---

UX Simplicity Principles

**Design Philosophy**: Users are stressed, unfamiliar with legal processes, and often have limited time/tech literacy. Every interaction must reduce cognitive load and legal anxiety.

**Guiding Standard**: "Can someone do this while standing in line at the grocery store?" (this is a bit extreme. A better example is if a user with one usable hand/arm can navigate the app, then a user with the use of both hands, but a kid or bag of groceries in the off hand will still be able to use the app effectively. An accessible app is easier to use for everyone).

Key UX Simplification Patterns

**Document Scanning (Bank Check Deposit Pattern)**

-   Real-time edge detection with alignment guides
-   Auto-capture when document properly positioned
-   Instant quality feedback ("Retake" vs "Looks good")
-   Multi-page scanning with thumbnail preview

**Case Type Selection (Decision Tree vs Dropdown)**

-   Plain-language questions: "What happened?" → "Someone is trying to evict me"
-   Progressive narrowing: 5-6 broad categories → specific case type
-   Visual icons for common cases
-   "Not sure?" button for AI assistance - more likely permanent input field or chat

**Form Filling (One Thing at a Time)**

-   Single question per screen (mobile)
-   Progress indicator (Step 3 of 12)
-   Plain language with legal term tooltips
-   Smart defaults based on previous answers
-   Auto-save after each answer

**Payment Flow (Consumer App Standard)**

-   Apple Pay / Google Pay / saved card options
-   Fee waiver qualification check **before** payment screen
-   Clear fee breakdown
-   One-tap "Pay $XX"

**Dashboard (To-Do List Pattern)**

-   Clear checklist with status indicators
-   ✓ Forms completed
-   ⏰ Court date: March 15 (Add to calendar)
-   📄 Response due by March 1 (3 days remaining)
-   Action buttons ("Complete form") not navigation
-   Red/yellow/green status indicators

**Court Date Management (Calendar Integration)**

-   One-tap "Add to Calendar"
-   Pre-event notifications (1 week, 1 day, 2 hours)
-   One-tap directions to courthouse

**Error Handling (Human, Not Technical)**

-   Plain language: "Your payment didn't go through. Try a different card?"
-   Not: "Transaction error code 4052"
-   Actionable solutions with visible help option

**Document Status (Package Tracking Pattern)**

-   Visual progress: Uploaded → Processing → Filed → Accepted
-   Push notifications at each stage
-   Estimated completion times

UX Success Metrics

-   Time to complete first filing (target: < 15 min for simple case)
-   Abandonment rate at each step (this is key to track pain points)
-   Mobile completion rate (should match or exceed web)
-   "Contact help" usage (lower = better UX)
