# Architecture Analysis

Decision-space analysis for moving beyond ITC demo toward real court adoption. Maps options and tradeoffs — not recommending yet.

## Table of Contents

1. [Hosting Model](#1-hosting-model)
2. [Frontend / Backend Coupling](#2-frontend--backend-coupling)
3. [Repo Structure](#3-repo-structure)
4. [AI Integration Boundaries](#4-ai-integration-boundaries)
5. [Agentic Tooling & Workflow](#5-agentic-tooling--workflow)
6. [Court Integration & Trust](#6-court-integration--trust)
7. [Modularity & Adoption Tiers](#7-modularity--adoption-tiers)
8. [Update & Patch Distribution](#8-update--patch-distribution)
9. [Open Source Strategy](#9-open-source-strategy)
10. [Cross-Cutting Concerns](#10-cross-cutting-concerns)

---

## 1. Hosting Model

The most architecturally consequential decision. Everything else flows from this.

### Option A: FLP-Hosted Multi-Tenant SaaS

FLP operates a central service. Courts get a tenant (branded subdomain or custom domain). FLP manages infra, deploys updates, handles AI costs.

**Examples:** Shopify, Zendesk, CourtListener itself

| Dimension | Analysis |
|-----------|----------|
| Infra cost | FLP bears all hosting costs. Scales with court count. AI API costs are the big variable — must either absorb, pass through, or rate-limit per tenant. |
| Dev velocity | Fastest to iterate. One codebase, one deployment. Ship a fix, every court gets it immediately. |
| Court IT burden | Zero. Courts configure via admin panel, not infrastructure. Huge selling point for under-resourced courts. |
| Customization | Limited to what the tenant config system exposes. Courts can't modify code. Branding (logo, colors, jurisdiction-specific content) — yes. Custom features — no. |
| Data sovereignty | Courts may have concerns about litigant data on FLP infrastructure. Some jurisdictions may have data residency requirements. Government procurement processes may require specific hosting (FedRAMP, StateRAMP). |
| Support burden | FLP owns all support. Court IT doesn't troubleshoot — they call FLP. Single point of failure = single point of blame. |
| Revenue model | Natural fit for subscription pricing. Per-court fees, tiered by usage/features. |
| Scaling | Must architect for multi-tenancy: tenant isolation, per-tenant rate limits, shared vs dedicated resources. Non-trivial. |
| Security | One deployment to secure. But a breach affects all courts simultaneously. Higher stakes. |
| AI costs | FLP pays LLM API costs for all courts. At scale: potentially $thousands/month. Need metering, quotas, or pass-through billing. |

### Option B: Court Self-Hosted (Open Source Install)

FLP publishes releases. Courts (or their IT vendors) deploy their own instance. Like WordPress self-hosted, or CKAN for open data portals.

**Examples:** WordPress.org, GitLab CE, Mastodon, CKAN

| Dimension | Analysis |
|-----------|----------|
| Infra cost | Courts bear hosting costs. FLP's cost is development + documentation + community support. |
| Dev velocity | Slower feedback loop. Courts may run different versions. Must maintain upgrade paths. Breaking changes are painful. |
| Court IT burden | Significant. Courts need staff or vendors who can manage Docker, PostgreSQL, DNS, TLS, monitoring. Many courts don't have this. |
| Customization | Maximum. Courts can fork, modify templates, add features. But custom forks create merge pain and version drift. |
| Data sovereignty | Courts own their data entirely. Strong selling point for government procurement. |
| Support burden | Courts manage their own infra. FLP provides docs, issue tracker, community forum. BUT: when courts struggle, they'll still ask FLP for help. "Works on my machine" problems multiply. |
| Revenue model | Hard to monetize directly (AGPL). Could offer paid support, managed hosting, or premium features. |
| Scaling | Each court scales independently. No multi-tenancy needed. But N courts = N different environments to reason about. |
| Security | Courts responsible for patching. Unpatched instances are a liability for the project's reputation even if not FLP's fault. |
| AI costs | Courts bring their own API keys. Simplifies FLP's cost structure. But onboarding friction: courts must set up Groq/OpenAI accounts. |
| Cloud requirement | No servers in closets. Self-hosted courts would need to use cloud providers (AWS, GCP, Azure, Fly.io, etc). Must document cloud deployment clearly. |

### Option C: Hybrid — Courts Host Portal, FLP Hosts AI/Services

Courts run the frontend/portal on their infrastructure. AI agents, document processing, and shared services live on FLP-operated infrastructure. Court portal calls FLP APIs.

**Examples:** Stripe (merchant hosts site, calls Stripe API), Auth0, Algolia

| Dimension | Analysis |
|-----------|----------|
| Infra cost | Split. Courts pay for their portal hosting. FLP pays for AI/service infrastructure. AI costs metered and billed to courts. |
| Dev velocity | Moderate. Can iterate AI services independently of court portal releases. But API contract between portal and services must be stable. |
| Court IT burden | Medium. Courts deploy a simpler application (no AI infra), but still need Docker/cloud skills for the portal. |
| Customization | Courts customize their portal freely. AI behavior configured via API params, not code changes. |
| Data sovereignty | Split concern. Litigant conversations flow through FLP's AI service — some courts may object. Could mitigate with ephemeral processing (no persistence on FLP side). |
| Support burden | Split but messy. "Is it the portal or the API?" finger-pointing. Need clear boundaries and good observability. |
| Revenue model | Natural fit for API usage pricing. Per-request, per-court, tiered. |
| Scaling | AI services scale centrally (FLP's problem). Portal scales per court. Good separation of concerns. |
| Security | API authentication between court instances and FLP services. API keys, mTLS, or OAuth. Another attack surface to manage. |
| AI costs | Centralized on FLP, billed out. Can negotiate volume discounts with LLM providers. Courts don't need their own API keys. |

> **Note (Feb 2026):** The hybrid model's court IT burden depends heavily on the frontend/backend coupling decision (#2). With a monolithic Django app, courts must run Django + PostgreSQL + Docker ("Medium" burden). With a decoupled static frontend (TS SPA), courts serve static files on their own domain — existing web infrastructure suffices. Court IT burden drops to near-zero, making hybrid significantly more viable. See [frontend decoupling proposal](frontend-decoupling-proposal.md) for analysis.
>
> **This is already FLP's operational model.** CourtListener runs as a centralized service on EKS (50+ k8s deployments, PostgreSQL/RDS, Elasticsearch, Redis, S3/CloudFront, 12 Celery worker pools, custom microservices including Doctor for document extraction). FLP serves 350+ courts' data through a single platform — external consumers access it via web or API. FLP does not deploy per-court instances. The hybrid model for the litigant portal maps directly onto this existing competency: FLP hosts the API/AI centrally (same pattern as CourtListener), courts serve static frontend files on their own domain (trivially easy, no new skills). The only new element is per-court API key/tenant configuration — analogous to CourtListener's existing per-user API throttling.

### Option D: Support All Models

Architecture flexible enough that courts choose SaaS, self-hosted, or hybrid.

| Dimension | Analysis |
|-----------|----------|
| Infra cost | Depends on which model each court picks. FLP's costs are unpredictable. |
| Dev velocity | Slowest. Must test all deployment topologies. Every feature needs to work in all modes. Config matrix explodes. |
| Court IT burden | Varies. But FLP must document and support all modes. |
| Customization | Maximum flexibility. But complexity tax on every feature decision. |
| Support burden | Highest. "How are you deployed?" becomes the first question on every support ticket. |
| Engineering cost | Significant. Multi-tenancy code + self-hosted packaging + API service extraction. Roughly 2-3x the deployment engineering of picking one model. |
| When it makes sense | If the project reaches significant scale (50+ courts) and different courts genuinely have incompatible requirements. Premature if optimizing for first 5-10 courts. |

### Hosting Model Summary

| Factor | SaaS (A) | Self-Hosted (B) | Hybrid (C) | All Models (D) |
|--------|----------|-----------------|------------|----------------|
| Court IT burden | None | High | Medium | Varies |
| FLP infra cost | High | Low | Medium | High |
| Dev velocity | Fast | Slow | Medium | Slowest |
| Customization | Low | High | Medium | High |
| Data sovereignty | Weak | Strong | Mixed | Flexible |
| Support burden | Medium | High | Medium-High | Highest |
| AI cost model | FLP absorbs | Court pays | FLP meters | Complex |
| Time to first court | Weeks | Months | Months | Many months |
| Engineering complexity | Medium | Medium | High | Very High |

---

## 2. Frontend / Backend Coupling

Currently: Django templates (Cotton components + Alpine.js) tightly coupled to Django views. CSRF tokens, template context, and server-rendered HTML make the frontend inseparable from the backend.

### Option A: Keep Django Templates + Build REST API Alongside

Keep the current server-rendered frontend as the "reference implementation." Incrementally build a REST API that exposes the same data/functionality. Both coexist in the same Django project.

| Dimension | Analysis |
|-----------|----------|
| Migration cost | Low. No rewrite. Add DRF/Ninja API views alongside existing template views. Current features keep working. |
| Two interfaces | Every feature exists twice: template view + API endpoint. Maintenance burden grows linearly. Risk of drift between them. |
| Frontend flexibility | Courts wanting a custom frontend can build against the API. Courts happy with the default get the Django templates. |
| SEO / initial load | Server-rendered templates win here. Important for public-facing court pages. |
| Developer experience | Django devs can work on templates. Frontend devs can work against the API. Lower barrier to contribution. |
| Timeline | Can start immediately. Non-disruptive. |
| Existing assets | Cotton component library (40+ components), Atomic Design system, Alpine.js integrations — all preserved. |
| Risk | API becomes second-class citizen if team is primarily Django-focused. Or templates rot if focus shifts to API consumers. |

### Option B: Full SPA + API Backend

Replace Django templates with a JavaScript SPA framework (React, Vue, Svelte, Next.js, Nuxt, etc). Django becomes a pure API server.

| Dimension | Analysis |
|-----------|----------|
| Migration cost | High. Rewrite all 40+ Cotton components, all page templates, all Alpine.js interactions in the new framework. Weeks to months of work. |
| Clean separation | Frontend and backend are truly independent. Any frontend can consume the API. Cleanest architecture for court customization. |
| Developer pool | JavaScript framework developers are abundant. But FLP's current stack knowledge is Django. Team capacity matters. |
| SEO / initial load | Requires SSR framework (Next.js, Nuxt) or pre-rendering. Added complexity. Pure SPA = bad for public court pages. |
| Accessibility | Must rebuild all WCAG AA compliance. Current Cotton atoms have it baked in. SPA frameworks need additional a11y discipline. |
| Infra complexity | Two deployable units (API server + static site / SSR server). CDN for static assets. CORS configuration. Auth token management instead of session cookies. |
| Cotton investment | Entire Cotton component library abandoned. Significant sunk cost. |
| Build tooling | Adds Node.js to the stack. Current project explicitly avoids Node (Tailwind CLI, no npm). This would reverse that decision. |

### Option C: Django Templates for Portal + API for Integrations

Keep Django templates as THE frontend (not just "reference"). Build API endpoints only for things that need programmatic access: AI agents, e-filing integrations, court data feeds, webhook callbacks.

| Dimension | Analysis |
|-----------|----------|
| Migration cost | Minimal. Only new API endpoints where needed. |
| Court customization | Courts customize via Django template overrides and CSS theming. Like Django admin customization. Not as flexible as "build your own frontend" but much simpler. |
| Simplicity | One codebase, one deployment, one framework. Easiest to maintain, test, and reason about. |
| Limitation | Courts that want a radically different UX must fork templates. Can't just swap in a React app. |
| Integration | API endpoints for machine-to-machine integrations (e-filing systems, case management systems, court calendars). Not for human-facing UI. |
| Open source | Most accessible to contributors. Django is well-known, single stack, low barrier. |

### Option D: Backend-for-Frontend (BFF) Pattern

Django serves as BFF — handles auth, sessions, server-rendered shell — but delegates to a frontend framework for interactive sections. Django renders the page skeleton, a React/Vue "island" handles the chat interface.

| Dimension | Analysis |
|-----------|----------|
| Migration cost | Medium. Only interactive sections (chat, document upload, sidebar) get rewritten. Static pages stay as Django templates. |
| Best of both | Server-rendered for SEO/speed on public pages. Rich interactivity where needed. |
| Complexity | Two rendering paradigms in one app. Build tooling for both. Devs need to know both. |
| Precedent | This is essentially what Alpine.js is already doing, just less formally. Alpine.js IS the "island" framework. The question is whether Alpine.js is sufficient or needs to be replaced. |
| Alpine.js reality check | Alpine.js handles the current chat interface well. Is there a concrete limitation driving the desire for something heavier? If not, this is over-engineering. |

### Frontend/Backend Summary

| Factor | Templates + API (A) | Full SPA (B) | Templates Only (C) | BFF Islands (D) |
|--------|---------------------|--------------|---------------------|------------------|
| Migration effort | Low | Very High | Minimal | Medium |
| Court UI flexibility | High | Highest | Medium | Medium |
| Maintenance burden | Medium-High | Medium | Low | Medium |
| Cotton preservation | Yes | No | Yes | Partial |
| Node.js required | No | Yes | No | Maybe |
| Contributor barrier | Low | Higher | Lowest | Medium |
| SSE/streaming support | Native | Needs work | Native | Native |

> **Note (Feb 2026):** Several assumptions in this section have shifted. See [frontend decoupling proposal](frontend-decoupling-proposal.md) for updated analysis accounting for:
> - **AI-assisted development** — rebuild cost drops from "weeks to months" to ~3-5 days; "team can't do TS" no longer holds in a Claude Code shop
> - **Hosting model interaction** — Option B (Full SPA) enables a much cleaner hybrid hosting model (Section 1, Option C) by reducing court IT burden to near-zero (static files vs. Django deployment)
> - **Migration effort for Option B** revised from "Very High" to "Low" with AI-assisted development

---

## 3. Repo Structure

Currently: monorepo with Django project + frontend assets + Docker + CI/CD.

### Option A: Stay Monorepo

Everything in one repo. Frontend, backend, docs, deployment configs.

| Pro | Con |
|-----|-----|
| Simple. One clone, one CI pipeline, one version. | Harder for courts to adopt only parts (e.g., just the API, not the frontend). |
| Atomic commits across frontend + backend. | Repo grows large over time. |
| Single PR for full features. | Contributors must understand full stack. |
| Easier dependency management. | |
| Already working. No migration cost. | |

### Option B: Multi-Repo Split

Separate repos: `litigant-portal-api`, `litigant-portal-ui`, `litigant-portal-agents`, etc.

| Pro | Con |
|-----|-----|
| Courts can adopt just what they need. | Cross-repo changes require coordinated PRs. |
| Independent versioning and release cycles. | Version compatibility matrix ("API v2.3 works with UI v1.8+"). |
| Teams can own repos independently. | More CI/CD to maintain. |
| Cleaner open source boundaries. | Contributor onboarding harder ("which repo do I start with?"). |
| | Premature unless team is large enough to warrant independent streams. |

### Option C: Monorepo with Packages/Modules

One repo, but internal packages with clear boundaries. Python namespace packages, npm workspaces, or similar.

| Pro | Con |
|-----|-----|
| Single repo simplicity. | Package boundaries require discipline to enforce. |
| Clear module boundaries without multi-repo overhead. | Still one clone for everything. |
| Can extract to separate repos later if needed. | Build tooling more complex than flat monorepo. |
| Supports modular adoption via installable packages. | |

### Repo Structure Signal

With a small team (FLP), monorepo is almost certainly correct for now. Multi-repo is a scaling decision, not an architecture decision. You split repos when coordination cost within the repo exceeds coordination cost between repos. That usually means 5+ regular contributors working on different subsystems.

---

## 4. AI Integration Boundaries

Where do we draw the line on modular adoption? We don't want to over-code to sell to everyone, some amount of AI needs to be accepted.

### Option A: AI Is the Product

AI chat and agentic tooling are the core value proposition. Courts can configure AI behavior (tone, jurisdiction, enabled agents) but can't remove it. Without AI, the portal is just a static info site — not worth the deployment effort.

| Pro | Con |
|-----|-----|
| Clear product identity. "This is an AI legal assistant." | Courts resistant to AI are excluded. |
| Simpler architecture — no feature flags for AI on/off. | AI costs are unavoidable for every deployment. |
| Every feature can assume AI is available. | Some courts may only want e-filing. |
| Strongest differentiation from generic court portals. | |

### Option B: AI-Optional, Feature-Flagged

AI features can be disabled entirely. The portal functions as a court information + e-filing system without AI. Feature flags control which AI modules are active.

| Pro | Con |
|-----|-----|
| Broadest adoption potential. | Feature flag complexity. Every template/view needs conditional logic. |
| Courts can start without AI, add it later. | Testing matrix: must test with AI on AND off. |
| Lower barrier to entry (no LLM API key needed). | Product identity diluted. "What is this tool, exactly?" |
| | Risk of building a mediocre generic portal instead of a great AI tool. |

### Option C: Tiered AI — Agents Required, Chat Optional

Agentic capabilities (document extraction, form filling, deadline tracking, e-filing assistance) are baked in. Conversational chat with litigants is a separate toggle.

| Pro | Con |
|-----|-----|
| Agents provide concrete, measurable value (extracted deadlines, filled forms). | Still requires LLM API access for agents. |
| Chat is the "scary" part for courts (liability, UPL concerns). Letting them disable it reduces adoption friction. | Drawing the line between "agent" and "chat" is blurry. |
| Courts can adopt AI without putting a chatbot in front of litigants. | Two AI modes to configure and support. |

### The "Where to Draw the Line" Framework

Instead of making AI binary (on/off), think about AI as layers:

```
Layer 0: Static content (no AI)
  - Court info pages, contact details, forms library
  - Any court can do this with WordPress. Not our value-add.

Layer 1: Smart document processing (agents, no user-facing AI)
  - PDF extraction, form auto-fill, deadline detection
  - AI runs behind the scenes. User sees structured output, not chat.
  - Lower UPL risk. Concrete, auditable outputs.

Layer 2: Guided workflows (agentic, semi-autonomous)
  - Step-by-step filing assistance, eligibility checkers
  - AI drives the flow, user makes choices
  - Medium UPL risk. AI suggests, user decides.

Layer 3: Conversational chat (full AI interaction)
  - Free-form legal Q&A with litigants
  - Highest value but highest risk (UPL, hallucination, liability)
  - Requires most court buy-in and legal vetting

Minimum viable adoption: Layer 1
Recommended: Layers 1-2
Full suite: Layers 1-3
Layer 0 alone: Not worth using this project
```

This gives courts a clear adoption ladder without requiring binary AI on/off architecture.

---

## 5. Agentic Tooling & Workflow

Current state: Agent framework exists with tool-calling support, but only DocumentExtractionAgent and WeatherAgent (demo) use tools. LitigantAssistantAgent is pure chat completion.

### Where Agentic Tooling Adds Value

| Agent Type | Purpose | Court Sensitivity | Technical Complexity |
|-----------|---------|-------------------|---------------------|
| Document Extraction | Parse uploaded PDFs to structured data | Low (behind the scenes) | Low (exists today) |
| Form Auto-Fill | Pre-populate court forms from extracted data | Low (user reviews before submit) | Medium |
| Deadline Tracker | Identify and track filing deadlines | Low (information, not advice) | Low-Medium |
| Eligibility Checker | Determine program eligibility (fee waivers, legal aid) | Medium (decision-adjacent) | Medium |
| Filing Assistant | Guide through e-filing steps | Medium (touches court systems) | High |
| Legal Q&A Chat | Answer legal procedure questions | High (UPL concerns) | Medium |
| Case Strategy | Suggest legal strategies | Very High (firmly UPL territory) | Medium |

### Architecture Implications

Agents need:
- **Tool registry** — pluggable tools per jurisdiction (Texas e-filing tools differ from Illinois)
- **Permission model** — which agents/tools are enabled per court deployment
- **Audit trail** — what the AI did, what tools it called, what data it accessed
- **Human-in-the-loop gates** — points where a human must approve before the agent continues

### Current Framework Assessment

The existing `Agent` base class + `Tool` system in `chat/agents/base.py` is solid:
- Tool-calling loop with configurable max_steps
- Structured tool output (response for LLM + data for frontend)
- Agent registry for multiple specialized agents
- LiteLLM abstraction for provider flexibility

What's missing for production agentic workflows:
- No persistent tool state across sessions
- No human approval gates (agent runs autonomously once triggered)
- No jurisdiction-aware tool selection
- No audit logging of tool executions
- No tool-level permissions (all-or-nothing per agent)

---

## 6. Court Integration & Trust

Litigants must believe this tool is sanctioned by their court. If it looks like a third-party app, adoption drops. If the court's name and branding aren't front and center, litigants won't trust the legal information.

### Branding Strategies

#### A: Subdomain / Custom Domain (SaaS Model)

`help.bexarcounty.gov` or `selfhelp.dupage.il.gov` pointing to FLP-hosted instance.

| Pro | Con |
|-----|-----|
| Appears as official court tool | Requires court IT cooperation for DNS |
| Court domain = instant trust | SSL certificate management for custom domains |
| Easy to implement (reverse proxy or SaaS platform pattern) | |

#### B: Embedded Widget (Hybrid Model)

Court embeds the AI assistant as an iframe or web component on their existing site.

| Pro | Con |
|-----|-----|
| Lives inside the court's existing website | Limited to widget-sized interactions |
| Court controls surrounding context | Cross-origin complications (cookies, CSP) |
| Low integration effort for courts | Can feel like a "chatbot popup" — low trust |

#### C: Themed Instance (Self-Hosted or SaaS)

Full portal with court-specific theme: logo, colors, jurisdiction name, local resources.

| Pro | Con |
|-----|-----|
| Complete branded experience | Theme system must be flexible enough |
| Court-specific content (local forms, local rules, local resources) | Content management becomes a concern — who updates jurisdiction-specific info? |
| Can include court-specific agents/tools | |

### Jurisdiction Configuration

Regardless of hosting model, each court deployment needs:
- Court name, logo, contact info
- Jurisdiction (state, county, court type)
- Local legal resources and referrals
- Applicable rules of procedure
- Available filing types and forms
- AI system prompt customization (jurisdiction-specific legal context)
- Enabled feature set

This configuration could live in:
- **Database** (admin panel) — easiest for SaaS
- **Environment variables / config files** — simplest for self-hosted
- **Config repo** — version-controlled, reviewable jurisdiction configs

---

## 7. Modularity & Adoption Tiers

### Proposed Module Boundaries

```
+---------------------------------------------------+
|                  PORTAL SHELL                      |
|   (auth, user profiles, navigation, theming)       |
|                                                    |
|  +----------+  +----------+  +---------------+    |
|  | Info Hub  |  | AI Chat  |  | E-Filing      |    |
|  |           |  |          |  |               |    |
|  | - Topics  |  | - Chat   |  | - Forms       |    |
|  | - FAQ     |  | - Stream |  | - Payments    |    |
|  | - Search  |  | - Agents |  | - Status      |    |
|  +----------+  +----------+  +---------------+    |
|                                                    |
|  +----------+  +----------+  +---------------+    |
|  | Document  |  | Case     |  | Court         |    |
|  | Tools     |  | Tracker  |  | Calendar      |    |
|  |           |  |          |  |               |    |
|  | - Upload  |  | - Cases  |  | - Hearings    |    |
|  | - Extract |  | - Tasks  |  | - Deadlines   |    |
|  | - Fill    |  | - Alerts |  | - Reminders   |    |
|  +----------+  +----------+  +---------------+    |
+---------------------------------------------------+
```

### Adoption Tiers

| Tier | Includes | AI Required | Target Court |
|------|----------|-------------|-------------|
| Starter | Portal shell + Info Hub + Document Tools | Yes (extraction only) | Courts dipping their toes in |
| Standard | Starter + AI Chat + Case Tracker | Yes (chat + agents) | Courts committed to AI assistance |
| Full Suite | Standard + E-Filing + Court Calendar | Yes (full) | Courts wanting end-to-end |

### The Over-Engineering Trap

**Signals you're over-engineering modularity:**
- Building config UI for feature combinations nobody has asked for
- Writing abstraction layers between modules that currently have 1 implementation
- Spending more time on the plugin system than on the features themselves
- Feature flags outnumber features

**Pragmatic modularity approach:**
- Django apps as module boundaries (already the case: `portal`, `chat`)
- `INSTALLED_APPS` + settings flags to enable/disable apps
- Don't build a plugin marketplace. Build good Django apps with clean imports.
- If two courts need different behavior, start with an `if` statement. Extract to a module after the third court needs it.

---

## 8. Update & Patch Distribution

How do courts get updates? Depends heavily on hosting model.

### SaaS: Automatic (FLP deploys)

| Pro | Con |
|-----|-----|
| All courts on latest version always | Courts can't opt out of changes |
| Security patches immediate | Breaking changes hit everyone at once |
| No version fragmentation | Requires robust staging/canary deployment |

### Self-Hosted: Release-Based

Courts pull updates from GitHub releases. Like upgrading a Django package.

| Pro | Con |
|-----|-----|
| Courts control when they update | Version fragmentation across courts |
| Can test updates in staging first | Courts may fall behind on security patches |
| No surprise changes | FLP must maintain upgrade migration paths |

**Patterns that help:**
- Semantic versioning with clear breaking change policy
- Database migration compatibility windows ("v3.x migrations work up to v4.2")
- `manage.py upgrade` command that handles migrations + static files + checks
- Release notes with "action required" flags

### Hybrid: Service Updates + Portal Releases

AI services updated by FLP (transparent to courts). Portal updates via release cycle.

| Pro | Con |
|-----|-----|
| AI improvements ship instantly | API version compatibility between portal and services |
| Portal stability for courts | Must maintain API backwards compatibility |
| Best of both worlds | API versioning discipline required from day one |

---

## 9. Open Source Strategy

AGPL-3.0 license. Others will fork, adapt, contribute.

### Audience Segments

| Audience | What They Want | How They Contribute |
|----------|---------------|---------------------|
| Courts adopting the tool | Working software, good docs, easy deployment | Bug reports, feature requests, jurisdiction configs |
| Court IT vendors | Clean API, themeable frontend, deployment docs | Integrations, deployment guides, bug fixes |
| Legal aid orgs | Jurisdiction-specific content, workflow customization | Content, translations, user testing |
| Civic tech developers | Good architecture, contribution guide, responsive maintainers | Features, bug fixes, new agents/tools |
| Other FLP projects | Reusable components, consistent patterns | Shared libraries, cross-project improvements |

### Mono-Repo vs Collection of Repos (Open Source Lens)

**Monorepo for open source:**
- Lower contributor barrier (one clone, one setup)
- But contributors must install full stack even to fix a template typo
- Issue tracker is simpler (one repo)
- BUT: forks carry everything, even parts they don't need

**Multi-repo for open source:**
- Courts can star/watch only what they use
- Smaller, focused repos are less intimidating to contributors
- BUT: "where do I file this bug?" problem
- Cross-repo features require contributor to understand multiple repos

### Fork-Friendly Architecture

If courts will fork, the codebase should make customization easy WITHOUT forking core code:

- **Theme/branding layer** — courts override CSS/templates, not Python code
- **Jurisdiction config** — courts add config files, not modify existing ones
- **Agent/tool plugins** — courts add agents to a directory, register in settings
- **Clear "don't modify" boundaries** — mark files as upstream-maintained vs locally-customizable

If the fork strategy works well, courts shouldn't NEED to fork. They should be able to:
1. Install the package
2. Create a jurisdiction config
3. Override templates for branding
4. Deploy

This is the Django app pattern (like how you'd customize `django-allauth` without forking it).

---

## 10. Cross-Cutting Concerns

### Cloud-Only Requirement

No servers in closets. This means:
- All deployment documentation targets cloud providers
- Docker images published to a registry (GHCR, Docker Hub)
- Terraform/Pulumi templates for common cloud providers (optional but valuable)
- Health checks, monitoring, and alerting baked in
- Managed database recommendations (not "install PostgreSQL on bare metal")

**Cloud provider matrix:**

| Provider | Ease | Cost | Gov't Friendly |
|----------|------|------|----------------|
| Fly.io | High | Low | Unknown |
| AWS (ECS/Fargate) | Medium | Medium | Yes (GovCloud) |
| Azure (Container Apps) | Medium | Medium | Yes (Gov) |
| GCP (Cloud Run) | High | Low-Medium | Yes (Gov) |
| DigitalOcean (App Platform) | High | Low | No |

Government contracts often require AWS GovCloud or Azure Government. Worth considering if target courts are government entities (they are).

### Observability

Multi-court deployments (any model) need:
- Structured logging (who, what, when, which court)
- Error tracking (Sentry or equivalent)
- AI usage metrics (tokens consumed, latency, error rates per court)
- User analytics (what features are used, where users drop off)
- Uptime monitoring

### Data Privacy

Litigant data is sensitive. Regardless of hosting model:
- PII handling policy (what's stored, how long, who can access)
- Data retention and deletion (right to be forgotten)
- Encryption at rest and in transit
- AI provider data policies (does Groq/OpenAI train on court data?)
- Audit logs for data access
- BAA (Business Associate Agreement) if health-adjacent info is discussed

### Internationalization

REQUIREMENTS.md mentions "global by design, i18n from the start." This affects:
- UI string extraction (Django i18n is built-in but templates need `{% trans %}` tags)
- AI system prompts per language
- Right-to-left (RTL) layout support
- Date/time/number formatting
- Legal terminology varies by country, not just language

---

## Decision Dependencies

Some decisions gate others:

```
Hosting Model (1)
  +-- gates -> Frontend/Backend Coupling (2)
  +-- gates -> Repo Structure (3)
  +-- gates -> Update Distribution (8)
  +-- gates -> Court Integration approach (6)

AI Integration Boundaries (4)
  +-- gates -> Modularity Tiers (7)
  +-- gates -> Agentic Tooling scope (5)

Frontend/Backend Coupling (2)
  +-- gates -> Open Source contribution model (9)
  +-- gates -> Hosting Model viability (1) ← bidirectional
```

Hosting model and AI boundaries are the two independent root decisions. Everything else follows from them.

> **Note (Feb 2026):** The dependency between Hosting (1) and Frontend/Backend Coupling (2) is bidirectional. The frontend coupling decision changes which hosting models are viable — a decoupled static frontend makes the hybrid model (1C) dramatically easier for courts by eliminating their need to run Django/PostgreSQL. See [frontend decoupling proposal](frontend-decoupling-proposal.md).

---

## Open Questions

These don't have clear answers yet and should be discussed:

1. **Who pays for AI inference?** At scale, LLM API costs are non-trivial. FLP absorbs? Courts pay? Per-interaction billing?

2. **Legal liability for AI output.** If the AI gives bad legal advice, who's liable? FLP? The court? The AI provider? This affects how much AI autonomy we allow.

3. **Court procurement process.** How do courts actually buy/adopt software? RFPs? Pilot programs? This affects whether SaaS subscription or self-hosted open source is more adoptable.

4. **FLP team capacity.** Supporting N courts on N hosting models requires significant DevOps/support capacity. What's realistic?

5. **E-filing integration scope.** Is e-filing in scope for this project, or is it a separate system that this portal links to? E-filing integrations are jurisdiction-specific, complex, and tightly regulated.

6. **Relationship to CourtListener.** How does this project relate to FLP's existing infrastructure? Shared auth? Shared data? Independent?

7. **Target court count.** Planning for 5 courts vs 500 courts leads to very different architecture decisions. What's the 2-year target?
