# Litigant Portal - Roadmap & Milestone Plan

## Current Snapshot (as of 2026-02-09)

### What's Built

**Core Platform:**
- Django 5.2 + Django Cotton component system (26 components, Atomic Design)
- Tailwind CSS v4, Alpine.js (standard build), mobile-first responsive
- Auth via django-allauth (login, signup, logout)
- User profiles (name, phone, address, county)
- Docker dev environment, Fly.io QA deploy (auto-deploy on push to main)
- CSP-compliant (no inline handlers), WCAG AA foundations

**AI Chat (the main feature):**
- Streaming AI chat via SSE (no WebSockets needed)
- Pluggable LLM providers: OpenAI (active), Groq, Ollama
- PDF document upload with LLM-powered extraction
- Conversation summarization
- Case sidebar with deadlines, action items, timeline
- System prompt engineering (attorney-at-self-help-center tone, UPL-compliant)
- Keyword search fallback when AI unavailable
- Rate limiting on all endpoints

**Test Coverage:** ~1,230 lines across portal + chat (models, views, services)

### ITC Demo Milestone - 3 of 13 formally closed

| Status | # | Title |
|--------|---|-------|
| CLOSED | #81 | User Legal Issue Discovery Flow |
| CLOSED | #78 | User court info |
| CLOSED | #77 | User current legal issue data set |
| OPEN | #47 | ITC Clickable Demo User flow implementation |
| OPEN | #32 | ITC Clickable Demo Plan |
| OPEN | #27 | [Parent] Clickable demo ready by ITC |
| OPEN | #72 | Tools: Semantic search for curated documents |
| OPEN | #80 | LP demo resolution |
| OPEN | #87 | Enhanced system prompt for eviction scenarios |
| OPEN | #88 | UI: Deadline and next-step components |
| OPEN | #89 | UI: Case sidebar panel |
| OPEN | #90 | Demo response caching for reliability |
| OPEN | #91 | Demo rehearsal and fallback plan |

**Note:** Many "open" issues are functionally complete on `itc-demo` (30+ commits ahead of main) but not formally closed.

### In-Progress Branch: `add-agents`

Already has foundational agent work:
- Base agent class
- Litigant assistant + weather (test) agents
- LiteLLM integration (simplified chat service)
- Updated message model for raw message storage
- Updated Alpine chat handler

### 18 PRs Merged to Date

From Docker setup -> chat -> layout -> auth -> sidebar -> doc upload -> tone refinement.

### Team

- 1 manager/lawyer (product + legal domain + UPL compliance)
- 1 full-stack dev (Django, infra, frontend)
- 1 AI engineer (agents, LLM integration, some full-stack)
- Additional expertise brought on as needed

---

## Phase 2: Post-ITC -> Court Pilot (6-12 month horizon)

**Goal:** Transform the successful ITC demo into a production system ready for a real court pilot with actual litigants. Court TBD.

**Gaps to close:** Real legal content, multi-case-type support, security & auth, reliability & monitoring, AI agentic tooling.

**Format:** Parallel theme tracks. Each track has a clear owner based on expertise, with cross-track dependencies called out.

---

### Track 1: AI Agent Infrastructure

**Primary owner:** AI Engineer | **Priority:** Highest (unblocks Tracks 2 & 3)

Everything else depends on a proper agent/tool framework. The `add-agents` branch gives us a head start.

**Phase A - LiteLLM + Agent Foundation (Month 1-2)**
- Merge `add-agents` branch work (LiteLLM, base agent, message model)
- #66 - LiteLLM integration: provider-agnostic LLM calls
- #67 - Agent abstraction: tool registration, multi-step reasoning
- #71 - Frontend standard for displaying tool calls/responses
- #54 - LLM safety parameter handling (legal content getting blocked)

**Phase B - AI Tools (Month 2-5)**
- #72 - Semantic search over curated legal documents (RAG)
- #73 - pgvector for embedding storage
- #70 - Memory: cross-session user context
- #69 - Case law search (integration TBD - CourtListener API?)
- #68 - Web search (for court websites, legal aid orgs)

**Phase C - AI Quality & Guardrails (Month 4-6)**
- Response evaluation/testing framework
- UPL compliance automated checks
- Hallucination detection for legal citations
- Multi-case-type prompt architecture (not just eviction)

---

### Track 2: Legal Content & Case Types

**Primary owner:** Manager/Lawyer + AI Engineer | **Priority:** High

The demo only covers eviction in DuPage County IL. A real pilot needs depth and breadth.

**Phase A - Content Architecture (Month 1-3)**
- Define document schema for legal resources (forms, rules, deadlines)
- Curate initial document corpus for pilot jurisdiction
- Build ingestion pipeline: legal docs -> embeddings -> pgvector
- Jurisdiction-aware system prompts (configurable per court)

**Phase B - Case Type Expansion (Month 3-6)**
- #26 - Eviction: harden from demo to production-quality
- Add 1-2 more case types (likely: small claims, family/divorce)
- Per-case-type: forms, deadlines, defenses, local rules
- #34 - Explore AI-assisted document assembly interviews

**Phase C - Pilot Jurisdiction Setup (Month 5-8)**
- Partner with target court (TBD)
- Court-specific: courthouse info, filing procedures, local rules
- Validate content accuracy with local attorneys
- #39 - Text message reminders for court dates (if pilot court wants it)

---

### Track 3: Production & Security

**Primary owner:** Full-Stack Dev | **Priority:** High (parallel with Track 1)

The demo runs on SQLite with minimal security. A court pilot needs the opposite.

**Phase A - Infrastructure (Month 1-3)**
- PostgreSQL migration (DATABASE_URL already supported)
- #58 - Alpine.js CSP build (remove x-html, server-side markdown)
- #74 - Standardize dev tooling (uv vs venv decision)
- #62 - Tox.ini vs .env cleanup
- CI/CD hardening: test suite in GitHub Actions
- Error monitoring (Sentry or equivalent)

**Phase B - Security & Auth (Month 2-4)**
- #33 - Court hosting trust/security story (documentation + implementation)
- Session management hardening
- Data retention policies (how long do we keep chat transcripts?)
- PII handling audit (user profiles, chat content, uploaded documents)
- Secure document storage (uploaded PDFs)

**Phase C - Reliability (Month 3-5)**
- Health monitoring and alerting
- LLM fallback chain (primary -> secondary -> keyword search)
- #90 - Response caching for common queries
- Load testing for expected pilot traffic
- Backup and recovery procedures

---

### Track 4: UX & User Flows

**Primary owner:** Full-Stack Dev + Manager/Lawyer | **Priority:** Medium (starts after Track 1 Phase A)

Evolve from demo UX to production UX that serves real users.

**Phase A - Polish & Accessibility (Month 2-4)**
- #8 - Mobile view (pilot users will be on phones)
- WCAG AA audit and fixes
- #99 - Dashboard vs Chat: define the logged-in experience
- #86 - Auto-generate style guide
- Onboarding flow for new users

**Phase B - Case Management (Month 4-7)**
- Case dashboard: view past conversations, action items, deadlines
- Case timeline: visual progress through legal process
- Document management: view/download uploaded documents
- #79 - E-filing integration (if pilot court supports it)

**Phase C - Outreach (Month 6-8)**
- #12 - Beta tester signup/onboarding
- Feedback collection mechanism
- Usage analytics (what questions do users ask most?)

---

## Immediate Next Steps (first 2 weeks)

1. **Close out ITC milestone** - Review `itc-demo` branch, merge to main, close done issues
2. **Demo retro** - Document what resonated at ITC, feedback received, new issues
3. **Triage `add-agents` branch** - Assess what's ready to merge vs needs rework
4. **Create GitHub milestones** for Phase A of each track
5. **AI Engineer onboarding** - Get familiar with codebase, `add-agents` branch ownership

---

## Cross-Track Dependencies

```
Track 1 Phase A (LiteLLM + Agents) --> Track 1 Phase B (AI Tools)
                                   --> Track 2 Phase A (Content needs RAG)
                                   --> Track 4 Phase A (Tool call UX)

Track 2 Phase A (Content Schema)   --> Track 1 Phase B (Semantic search needs docs)

Track 3 Phase A (PostgreSQL)       --> Track 1 Phase B (pgvector needs PG)
```

**Critical path:** Track 1 Phase A -> Track 3 Phase A (PostgreSQL) -> Track 1 Phase B (pgvector/RAG)

---

## Open Questions

- Which case types beyond eviction should we target for the pilot?
- CourtListener API for case law search - what's the integration story?
- Data retention: how long to keep chat transcripts, uploaded docs?
- Hosting: Fly.io for pilot, or does the court need on-prem/gov cloud?
- Budget for LLM API costs at pilot scale?
