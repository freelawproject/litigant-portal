# Frontend Decoupling: Three-Viewpoint Analysis

This breakdown assumes the backend API split is decided — Django becomes API-only (Django REST, FastAPI, or similar). The question is **whether to rebuild the frontend in TypeScript now**, or keep Django templates and defer.

---

## Where We Are

**Timeline:** Next client-facing deliverable is March. All demos between now and then are dev/QA only.

**Codebase:**
- **40 Cotton components** (12 atoms, 11 molecules, 8 organisms) + 9 pages/auth templates
- **5 API endpoints already exist** (`/api/chat/stream/`, `/api/chat/status/`, `/api/chat/upload/`, `/api/chat/summarize/`, `/health/`)
- **chat.js** (753 lines) is the only substantial JS — handles SSE streaming, file upload, timeline state
- **Design tokens** live in `src/css/main.css` (Tailwind v4 CSS-based config) — framework-agnostic
- **API gap is small**: enable allauth headless (installed, not configured), add 2 profile endpoints, convert search to JSON
- **WCAG AA** is a hard requirement (court adoption depends on it)
- **Target users**: stressed, low-tech-literacy litigants on old smartphones. Mobile-first.

---

## The Claude Code Shop Reality

The org uses Claude Code daily for coding, code reviews, PR reviews, test writing, documentation, and planning. This changes foundational assumptions that all three viewpoints must account for.

| Traditional Assumption                 | Claude Code Reality                                                                                                                                                           |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "We're a Python org — we can't do TS"  | The org is a Claude Code org. Python is the backend language by choice, not an identity. Any dev can work in TS via Claude the same way they work in Python via Claude today. |
| "We don't have TS reviewers"           | Claude reviews TS as effectively as Python. If it already does PR reviews, TS PRs get the same treatment.                                                                     |
| "Two build systems = complexity"       | Claude handles Node/npm, bundler config, and CI/CD trivially. The cognitive overhead is real but small when AI manages it.                                                    |
| "Only the solo dev can maintain TS"    | Any dev can maintain either stack via Claude. The bus factor is mitigated by AI itself.                                                                                       |
| "Adding Node adds onboarding friction" | Claude sets up dev environments. A new contributor runs `claude` and asks how to get started.                                                                                 |

**What doesn't change:** Courts don't care about the tech stack. WCAG AA must be re-earned regardless of language. Shipping features matters more than architecture. Claude helps write accessible code but doesn't guarantee it.

**The argument cuts both ways.** If Claude makes any language equally maintainable, then maintaining Django templates via Claude is just as easy as maintaining a TS frontend via Claude. The Claude Code reality weakens the objections to TS, but it also weakens the case *for* TS. Language choice has to stand on its own merits beyond "Claude handles it."

---

## Viewpoint 1: Solo Dev (JS/TS Background)

**Core argument:** TypeScript has the strongest ecosystem for UI work. In a Claude Code shop, language choice should optimize for the problem domain, not the team's historical language.

### Traditional version of this argument

*"I write Python through AI. TypeScript is my native language. The bus factor is real — if AI changes, I can't maintain Django templates."*

### How Claude Code changes it

The bus factor argument weakens. In a Claude Code shop, if AI tooling degrades, the *entire org* is affected — not just the frontend. Everyone writes code through AI. The risk isn't language-specific.

But the argument gets **replaced by a stronger one**: ecosystem fit. UI development has richer tooling in TS — Storybook (component docs + visual testing), axe-core (automated a11y in CI), TypeScript compiler (catches prop/state/API contract bugs Django templates silently swallow).

### What holds

- **Native + AI > AI alone.** I can work in TS natively and with Claude. For Python I rely on Claude alone. That's not a dealbreaker, but native understanding still matters for debugging, incident response, and architectural decisions where AI is slower than intuition.
- chat.js is already 95% framework-portable. SSE logic, upload flow, timeline state — all transfers intact.

### Honest risks

- I'm biased. The motivation started as preference and found supporting evidence. Choosing the best ecosystem for the domain (UI = TS) is rational, but I should own the starting point.
- **The tooling gains are aspirational, not guaranteed.** Storybook, axe-core, visual regression testing — none of these exist in the project today. Teams that haven't set up automated a11y testing in their current stack often don't do it in the new one either. The framework isn't the bottleneck — the discipline is. (Note: axe-core runs against any rendered HTML. It can be adopted today without a rebuild.)

---

## Viewpoint 2: Boss / Company (Python Big Data Shop)

**Core concern:** We have 40 working, accessible components that shipped a real demo to courts. The proposal is to rebuild them in a different language for tooling benefits we haven't needed yet.

### Traditional version of this argument

*"We're a Python org. We can't review TS. Two build systems. The current stack works. This serves one dev's preferences."*

### How Claude Code changes it

Most of the traditional objections collapse (see table above). "Can't review TS," "two build systems," and "we're a Python org" all assumed human-only workflows. In a Claude Code shop, these aren't real barriers.

The open source contributor argument also flips: JS/TS is the most widely used language on GitHub by a large margin. A TS frontend likely *widens* the contributor base, not narrows it. FLP's existing Python community (CourtListener, RECAP) is a narrow pool.

### What still holds

- **The current stack isn't blocking anything.** The ITC demo shipped. Courts saw it. What's blocking adoption is court procurement processes and legal liability (see architecture-analysis.md, Open Questions 1-3) — not the frontend framework.
- **Opportunity cost is never zero.** Even with no client-facing deadline until March, the 2-4 weeks of rebuild time could be spent on the March deliverable, on axe-core in CI against existing templates, on E2E tests with Playwright, or on backend features (guided workflows, document tools) that directly advance court adoption.
- **The "any Python dev can maintain TS via Claude" claim is untested.** Has anyone else on the team actually tried writing, reviewing, or debugging TypeScript through Claude Code? This should be validated before betting the frontend on it.

### What actually matters for this view

The company's real question isn't "can we do TS?" — it's **"what's the actual cost, and what are we not doing instead?"** The rebuild window has low external visibility cost, but the opportunity cost of the work not done matters.

---

## Viewpoint 3: Neutral Consultant (Project Needs Only)

**Framework:** What maximizes the portal's chance of reaching litigants in courtrooms?

### Traditional version of this argument

*"Minimize complexity. Fewest moving parts. One language, one stack. Don't rebuild working software."*

### How Claude Code changes it

The "complexity" of a second language is reduced when AI makes developers polyglot. But it doesn't reach zero — the argument cuts both ways (see note above). The question shifts from **"can the team work in TS?"** to **"does TS provide better tooling for UI work?"** It does — but some of those tooling gains (axe-core) are available without a rebuild.

### What still holds

1. **Ship speed.** Courts evaluate working demos, not architecture docs. The March deliverable should not slip for a frontend rebuild.
2. **Accessibility is a real project, not a line item.** The current Cotton components have detailed ARIA attributes, focus management, keyboard handling, and screen reader support baked in. Rebuilding all of this is 30-50% of the total frontend effort — not something that happens automatically in a component port.
3. **Court adoption.** Courts care about: Does it work? Is it accessible? Can we brand it? Is it maintained? They do not care whether the frontend is Cotton or React.

### Honest timeline

The component port alone is fast (~3-5 days). But a production-ready frontend rebuild includes work the component estimate doesn't cover:

| Included in "3-5 days" | Not included |
|------------------------|-------------|
| Component port (atoms, molecules, organisms) | Project setup (bundler, linting, test framework, CI) |
| Basic page layouts | Auth integration (session → token-based, CSRF changes) |
| chat.js adaptation | WCAG AA re-certification (ARIA, focus, keyboard, screen reader) |
| | Routing (6+ routes currently handled by Django) |
| | Rewriting test suite (20+ integration tests become worthless) |
| | CSP compliance in the new framework |
| | CORS, environment config, Docker setup |
| | Error handling, loading states |

**Realistic estimate:** 2-3 weeks for feature parity. 4-6 weeks for full quality parity including accessibility and testing. The rebuild is still a bounded project, not months of work — but it's not a sprint either.

### Recommendation

**Phase 1 — API-first backend (do now, ~2-4 days).** Universally valuable regardless of frontend decision:
- Enable allauth headless mode
- Add profile API endpoints
- Convert search to JSON
- Document the full API contract (OpenAPI/Swagger)
- Django templates keep working unchanged

**Phase 1.5 — Adopt tooling gains without a rebuild.** Some of the TS ecosystem benefits are available today:
- Add axe-core to CI against existing rendered HTML (works with any framework)
- Add Playwright E2E tests against existing pages
- These improve quality now and become the acceptance criteria for any future frontend

**Phase 2 — TS frontend rebuild (after March deliverable).** Sequence:
1. Chat page first (most decoupled, validates the approach)
2. Auth pages (simplest, tests allauth headless)
3. Profile, then dashboard
4. Remove Django templates last — never cut over until the new frontend passes the axe-core and E2E tests from Phase 1.5

---

## Summary Table

| Dimension             | Solo Dev View                                  | Company View                                                          | Consultant View                                                        |
| --------------------- | ---------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Frontend choice       | TypeScript (any framework)                     | Weighing opportunity cost vs. long-term gain                          | TypeScript — but after March, not before                               |
| Strongest argument    | Best ecosystem for UI + native fluency         | Working accessible components exist; what's the actual cost?          | API-first backend is universally valuable; frontend rebuild can wait   |
| Traditional objection | "I'm biased"                                   | "We can't do TS"                                                      | "Don't add complexity"                                                 |
| Claude Code response  | Ecosystem fit is rational, not just preference  | Cuts both ways: if Claude makes TS easy, it makes Django easy too     | Reduces language switching cost but doesn't make rebuilds free         |
| What still holds      | Native understanding > AI-only for debugging   | Opportunity cost; tooling gains are aspirational; untested team claim  | WCAG AA is 30-50% of the work; axe-core works today without a rebuild |
| Key risk              | Tooling aspirations may not materialize         | Rebuild takes 2-4 weeks, not 3-5 days                                | March deliverable slips                                                |

---

## Downstream Implication: Hosting Model

The frontend decoupling isn't just a developer experience decision — it unlocks a hosting architecture that makes court adoption materially easier.

The [architecture analysis](architecture-analysis.md) evaluates a hybrid model (Option C): courts host the portal, FLP hosts AI/services. With a monolithic Django app, "hosting the portal" means courts run Django + PostgreSQL + Docker — rated "Medium" court IT burden. Many courts can't do this.

With a decoupled TS frontend, the split changes:

| Layer            | Who hosts                | What it requires                                                        |
| ---------------- | ------------------------ | ----------------------------------------------------------------------- |
| Static frontend  | Court, on their own domain | Static files on any web server or CDN. Courts already do this.         |
| Backend API + AI | FLP, centrally managed     | Database, LLM access, auth, streaming, file processing — the hard part. |

Court IT burden drops from "Medium" to **low** (not zero — courts still manage API keys, CORS configuration, SSL certificates, and frontend version updates).

This resolves several open concerns from the architecture analysis:

- **Court trust/branding** — portal lives on the court's domain
- **Data sovereignty perception** — courts feel ownership over their portal
- **Update distribution** — FLP pushes API updates transparently; frontend updates are new static builds courts pull
- **AI cost model** — FLP meters API usage per court, natural billing boundary at the API layer
- **Support boundary** — cleaner split than a monolith, though not entirely clean (version compatibility between court frontend and FLP API requires coordination)

**Risk not previously addressed: API versioning.** The moment courts run their own frontends against FLP's API, breaking API changes require coordinating with every court. This is a support and engineering burden that scales linearly with court count. An API versioning strategy (semantic versioning, deprecation windows, backwards-compatible changes) must be in place before the first court deploys.

This hosting model **requires** the frontend decoupling. Django templates can't be served from a court's CDN — the frontend IS the backend in a monolith. The TS rebuild is what makes the hybrid hosting viable.

### This is already FLP's operational model

CourtListener validates the centralized API pattern. FLP already operates as a centralized service provider:

- **Production EKS cluster** (Kubernetes on AWS) with 50+ deployments, auto-scaling, and full CI/CD
- **Custom microservices** — Doctor (document extraction/OCR), Inception (ML embeddings), Disclosure Extractor. The litigant portal's document processing needs are a natural extension.
- **40+ REST API endpoints** with versioning, throttling, webhooks, and bulk data exports
- **Data infrastructure** — PostgreSQL (RDS), Redis (ElastiCache), Elasticsearch, S3/CloudFront CDN
- **12 Celery worker pools** for distributed task processing (scraping, indexing, document processing)
- **350+ courts' data** served through a single centralized platform

CourtListener's model is: FLP hosts the platform centrally, external consumers (researchers, journalists, lawyers, courts) access it via web or API. FLP does NOT deploy per-court instances. The hybrid model for the litigant portal is the same pattern with a different frontend delivery mechanism.

**The responsibility line maps to existing competency:**

| FLP controls (already does this)       | Courts control (low burden)            | Neither needs to manage        |
| -------------------------------------- | -------------------------------------- | ------------------------------ |
| API servers (Django/FastAPI)           | Static frontend on their domain        | Per-court server deployments   |
| AI/LLM agents + orchestration         | DNS/SSL (already manage this)          | Court-side Docker/Kubernetes   |
| Database (PostgreSQL on RDS)           | Branding (CSS vars, logo, content)     | Database administration        |
| Document processing (Doctor exists)    | API keys + CORS config                 |                                |
| Auth service (allauth headless)        | Frontend version updates               |                                |
| Search (Elasticsearch)                 |                                        |                                |
| Monitoring, scaling, CI/CD            |                                        |                                |
| API versioning + backwards compat      |                                        |                                |

**Important distinction:** CourtListener serves external consumers who access FLP's platform. The hybrid model has courts deploying a frontend that talks to FLP's backend — that's closer to Stripe's model (merchant hosts site, calls Stripe API). Stripe invests heavily in client libraries, documentation, developer experience, and support for this model. FLP should plan for this support burden as court count grows.

---

## Outside Gut Check (CTO Review)

An independent review challenged several assumptions in this analysis. Key corrections incorporated above:

1. **The Claude Code argument is circular.** If AI makes any language equally maintainable, it weakens both the case against TS and the case for it. Language choice must stand on ecosystem merits, not "Claude handles it."

2. **The 3-5 day estimate was the component port, not the project.** Full production-ready rebuild including auth, testing, accessibility, routing, and infrastructure is 2-4 weeks. Still bounded, but not a sprint.

3. **WCAG AA is 30-50% of the frontend effort.** The current Cotton components have detailed a11y baked in. Re-earning it is a real workstream, not a checkbox.

4. **axe-core doesn't require a rebuild.** It runs against any rendered HTML. The biggest tooling win can be adopted today against existing Django templates.

5. **The hosting model is real but oversold.** Court IT burden drops from "Medium" to "Low," not "near-zero." Courts still manage API keys, CORS, SSL, and version updates. API versioning becomes a scaling concern.

6. **Three viewpoints arriving at the same conclusion is one opinion in three hats.** The company view needed a real strongest argument — not "we can't do TS" (which Claude collapses) but "we have working accessible components and want to rebuild them for benefits we haven't needed yet."

7. **Opportunity cost is never zero.** Even with no client-facing deadline, the time has alternative uses: March deliverable, axe-core in CI, E2E tests, backend features.

---

## References

### This repo
- [Architecture Analysis](architecture-analysis.md) — Section 2 (Frontend/Backend Coupling), Section 1 (Hosting Model), Open Questions
- [ARCHITECTURE.md](ARCHITECTURE.md) — Tech stack rationale, CSP compliance, Alpine.js/Cotton decisions
- [Requirements](REQUIREMENTS.md) — MVP scope, post-MVP features, success metrics
- [Component Library](COMPONENT_LIBRARY.md) — Current Cotton component inventory, a11y testing approach
- [Security](SECURITY.md) — CSP configuration, pre-commit hooks, production headers
- [Demo Flow](demo-flow-jane.md) — ITC demo user journey (Jane's 8-step flow)
- [Chat Plan](chat-plan.md) — SSE architecture, chat.js analysis, server-side markdown
- [Expert Feedback](expert-feedback/2026-01-15-lawyer-eviction.md) — Lawyer review of demo flow

### FLP infrastructure (source for hosting model analysis)
- [CourtListener](https://github.com/freelawproject/courtlistener) — Production Django app: EKS deployment, 40+ API endpoints, Doctor/Inception microservices, 12 Celery worker pools
- [Kubernetes manifests](https://github.com/freelawproject/kubernetes) (private) — 50+ k8s deployments, HPA configs, service definitions
- [Free Law Project](https://free.law) — Organizational mission, operational model, centralized service pattern
