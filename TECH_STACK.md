# Litigant Portal - Technical Stack Overview

## Current Team Strengths

Free Law Project has deep expertise in:

-   **Backend**: Python/Django, SQL databases, court data scraping and normalization
-   **Frontend**: Django Cotton components, AlpineJS, TailwindCSS (currently used in CourtListener)
-   **Domain Knowledge**: Multi-jurisdictional legal data, court systems

**Reference**: [CourtListener's New Frontend Architecture](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)

---

## Key Decision: Platform Strategy

### Option A: Web-First (Django + Progressive Web App)

Build on existing Django/Cotton/AlpineJS stack, make it mobile-responsive, add PWA features over time.

**Pros**:

-   Leverages team's existing expertise - fastest path to MVP
-   Single codebase works on all devices (desktop, mobile, tablet)
-   Deploy updates instantly without app store approval
-   Universal access - no installation required, works in any browser
-   Lower development cost - one team, one codebase
-   Achievable within 3-month prototype timeline

**Cons**:

-   Mobile experience won't match native app polish
-   iOS restricts some PWA features (push notifications, background sync)
-   Less discoverable without app store presence
-   Users may perceive web apps as "less professional" than native apps

---

### Option B: Native Mobile Apps (iOS + Android)

Build separate native apps in Swift/Kotlin consuming Django backend APIs.

**Pros**:

-   Best possible mobile user experience
-   Full access to device features (camera, sharing, offline sync)
-   App store presence for discoverability
-   Professional polish users expect

**Cons**:

-   Team has no current mobile development expertise
-   3x development effort (iOS + Android + Web for desktop)
-   Slower iteration - app store reviews delay updates
-   Significantly extends timeline (6-9 months minimum for MVP)
-   Higher ongoing cost - need to hire/contract mobile developers

---

### Option C: Hybrid Framework (React Native / Flutter)

Use cross-platform framework to share code between iOS and Android.

**Pros**:

-   Share ~70% of code between iOS/Android
-   Single mobile development team
-   Access to native device features

**Cons**:

-   Team must learn entirely new framework (React Native or Flutter)
-   Cannot leverage existing Django Cotton/AlpineJS expertise
-   Separate codebase needed for desktop web experience
-   Framework dependency and maintenance risk
-   Still extends timeline beyond 3 months

---

## Recommendation: Progressive Strategy

### Phase 1 (MVP - 3 months)

Start with **Web-First** approach using existing Django stack:

-   Mobile-responsive design works on all devices immediately
-   Validate core value proposition with familiar technology
-   Gather user feedback on mobile experience
-   Baseline: file uploads, basic camera access work in mobile browsers

### Phase 2 (3-6 months)

Add **PWA enhancements** if Phase 1 mobile usage is strong:

-   Offline capability
-   Install to home screen
-   Native-feeling sharing and uploads
-   Measure adoption and engagement

### Phase 3 (Post-MVP)

Decide on native apps based on **data**:

-   What % of users primarily access via mobile?
-   What features do users request that PWA can't provide?
-   Do we have resources to maintain multiple platforms?

---

## AI Integration Approach

### Hybrid Cloud/Local Model

**Cloud APIs** (Anthropic Claude, OpenAI):

-   **Pros**: Best quality, no infrastructure management, scalable
-   **Cons**: Per-use costs, data sent to third parties, privacy concerns

**Local Deployment** (Ollama, open-source models):

-   **Pros**: Complete privacy, works offline, no per-use costs
-   **Cons**: Lower quality, requires powerful hardware, user manages deployment

**Strategy**: Offer both options. Let users choose based on their privacy preferences and resources.

---

## Security & Privacy

### Cloud Security Reality

Modern cloud platforms offer sophisticated security that most organizations cannot match on-premise:

-   Virtual Private Clouds (isolated networks)
-   Customer-managed encryption keys (provider can't access data)
-   Compliance certifications (HIPAA, FedRAMP, SOC 2)
-   Regional data residency

### Addressing Perception

While cloud security is technically strong, **user trust matters**:

-   Some jurisdictions/users will distrust cloud processing of legal documents
-   Solution: Offer both cloud deployment (default) and self-hosted option
-   Clear transparency about where data is stored and processed

---

## Open Questions for Discussion

1. **Mobile Priority**: How critical is native mobile app experience vs getting core features working quickly?

2. **AI Trade-offs**: What's the right balance between AI quality (cloud) and privacy (local) for MVP?

3. **Document Scanning**: Do we need professional-grade scanning in MVP, or is basic upload sufficient?

4. **Timeline vs Features**: Is 3-month web MVP acceptable, or do stakeholders require native mobile from day one?

5. **Deployment Model**: Should we build self-hosted option in parallel with cloud deployment, or wait for demand?

---

## Next Steps

1. Build basic prototype with Django Cotton stack (leverage existing expertise)
2. Test mobile experience in real-world conditions
3. Gather user feedback on what mobile features matter most
4. Make data-driven decision on native app investment

---

_This is a stakeholder-level summary. Technical details will be documented separately as decisions are finalized._
