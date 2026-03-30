# Demo Strategy: Full Flow Without AI Tools

## Problem

The beta demo needs to show the complete arc — Jane arrives → describes her situation → facts surface → action plan assembles → she can act on it. But the AI tools (RAG, case law search, web search, MCP tooling) and court corpus won't be ready in time.

## Approaches

### 1. Enhanced System Prompt as "Fake RAG"

Bake DuPage County eviction knowledge directly into the system prompt — statutes, notice periods, ILRPP eligibility thresholds, court address/hours, filing requirements. The LLM already knows most of this from training data; the prompt makes it reliable and specific.

When real RAG lands, the prompt shrinks and the knowledge comes from API calls instead. The conversation quality is nearly identical for the demo.

**Covers:** Issue spotting, fact discovery, eligibility surfacing, filing requirements.

### 2. Fixture-Driven Action Plan

The sidebar/action plan (#193) renders from structured data. After the AI finishes issue spotting (via `UpdateCaseFacts`), a new `UpdateActionPlan` tool call populates the action plan with fixture-quality data — deadlines, checklist items, resources. The "knowledge" comes from the prompt rather than RAG.

**Covers:** Stages 5–8 of the legal flow (guided next steps → resolution).

### 3. Seeded Briefcase for Demo Fast-Forward

A management command (`manage.py seed_jane_demo`) that pre-populates a briefcase at any stage of Jane's journey. Demo presenter can start fresh or jump to "Jane has uploaded her notice, facts are captured, action plan is assembled" and show the resolution phase directly.

**Covers:** Court partner demos where you don't want to wait for a live AI conversation.

## Recommended Sprint Plan

1. **#87 prompt work** — DuPage eviction knowledge in the system prompt (highest leverage, makes the whole flow feel real)
2. **New tool: `UpdateActionPlan`** — schema for action items, deadlines, resources, checklists. Same pattern as `UpdateCaseFacts`, same SSE pipeline, writes to a different part of the briefcase
3. **Fixture/seed command** — pre-populated case at each stage of Jane's journey

## Key Insight

The prompt _is_ the temporary RAG. When real tools land (#68, #69, #70), the prompt knowledge gets replaced by API calls, but the tool schemas, display components, and briefcase models stay the same. Nothing gets thrown away.

## Related Issues

- #87 — Enhanced system prompt for eviction scenarios
- #177 — Briefcase: unified session state model
- #179 — Court-configurable topic context
- #193 — Action plan sidebar
- #197 — Research/POC: court-configurable schemas
- #68–#70 — nadahlberg's AI tool issues (web search, case law search, memory)

## References

- [Legal Flow](overview-mapped-legal-flow.md) — 9-stage flow
- [Happy Path](happy-path-jane.md) — what the AI surfaces for Jane
- [Demo Flow](demo-flow-jane.md) — 8-step abbreviated demo
