# Litigant Portal - Architecture

## Vision

Democratize access to justice by empowering self-represented litigants with AI-augmented legal guidance, education, and document preparation tools.

**Core Principles:**

- Global by design (i18n from the start)
- WCAG AA accessibility as requirement
- Mobile-first (users on older phones)
- Human-centered AI (augments, not replaces)
- Open contracts (producer-agnostic, validated at the boundary)
- Low-friction for partners — the deploying court is a client too, and needs "easy mode" as much as the litigant does. Minimize what a partner must operate: one hostname (one CNAME), services routed by path not subdomain, portable across partners and self-hostable. A `.gov` DNS change is a ticket and a wait; design so they rarely need one.

---

## Open Contracts (Interface-Driven Design)

Litigant Portal is open source, and a court partner can stand up their own hosted instance. So we design around **explicit, validated data contracts** — schemas, file formats, API shapes — not around a particular producer or UI. Any compliant producer works identically: hand-authored files, a partner's own CMS, an AI-authoring tool, or direct API calls. LP depends only on the contract; validation at the boundary enforces it, and how the data was produced stays entirely on the producer's side of that line.

**Example — A2J Document Assembly Tool (DAT).** The DAT expects three inputs: a base PDF, a key/value answer set, and an overlay `.json` mapping each answer to coordinates on the PDF (where each value renders to "fill it in"). Those files can come from the A2J Viewer's guided-interview flow _or_ be POSTed straight to the API endpoint with Postman — either path returns an assembled PDF. The tool depends on the contract (the three file formats), never on how they were produced.

**In LP today.** The Topic Flow corpus is exactly this: `schema.py` (`extra="forbid"`) + the loader's id cross-reference checks + the `checks.py` startup guard _are_ the partner-facing contract. A conformant corpus flows through one validated path regardless of what authored it; a non-conformant one fails loudly at the boundary.

### One hostname, path-routed services

A court partner gives us **one CNAME** (`portal.theircourt.gov`) and _everything_ runs under it — the LP app at `/`, add-on services by path. We do **not** put add-ons on their own subdomains, because each subdomain is another DNS record a court's IT has to create and maintain, and partner DNS friction is real (a `.gov` change is a ticket, not a self-serve edit). Path-routing keeps a partner's deployment to a single record, makes it portable across partners, and means an open-source self-hoster does nothing extra.

Concretely: the docassemble document-assembly handoff is served at `<host>/interview/` (not `interview.<host>`), reverse-proxied by Caddy to the docassemble container, with docassemble told its URL root via `POSTURLROOT` (#550). We pay the sub-path complexity once, at our layer; every partner and self-hoster gets the simple deployment. New add-on services should follow the same rule — claim a path, never require a new hostname.

### Topic Flow → docassemble handoff contract

The `packet` output hands off to a [docassemble](https://docassemble.org) interview that fills the actual court forms. Two systems, two jobs, one contract — and a deliberate split of _which_ facts each side owns:

- **Topic Flow owns** the light fact set it already needs for deadlines and the summary recap, named to match the interview's variables 1:1 so a future prefill is lossless (no ambiguous name-splitting). These `fact_gather` question ids are the contract:
  `current_first` · `current_middle` · `current_last` · `requested_first` · `requested_middle` (· `requested_last`, standard track only — the waiver track leaves the last name unchanged) · `filing_county` · `publication_date`.
- **The interview owns** the full document fact set Topic Flow never collects: residence street/city/zip, residency-since, citizenship, criminal history, publication newspaper, and any track-specific fields. Asking these in the AI-free flow would duplicate the interview and bloat a deliberately light surface.

Names are collected as structured first / middle / last (not a single free-text field) precisely because the forms and the interview are structured that way — splitting a combined name string back apart is lossy and ambiguous.

**v1 is link-out + manual return, no prefill** (#543): the flow links out to the interview, the litigant completes and downloads their packet there, then returns to LP for filing steps. The prefill seam — POSTing this answer set to start a prefilled session, keeping PII out of the URL — is the deferred v2 (#531), and an AI-free session-state "Briefcase" (#177) is the natural carrier for it. The contract above is what makes that future drop-in: same ids, no rework.

---

## Topic Flow: Linear Structure, Forks at the Entry Point

Applies to the **non-AI Topic Flow engine** (AI chat flows are a separate model, out of scope here).

The engine renders one fixed, ordered corpus per `(court, topic, role)` as a single scrollable page. It has **no conditional/branching logic** — `fact_gather` answers drive deadline math and display (e.g. the summary) only, never which sections show. So a legal process with multiple procedural paths is modeled as **separate corpora selected by distinct URLs**, and the path-selection decision is pushed up to the linking surface — a court links straight to the right track from its own website. Each track corpus cross-links to the others in prose for mis-clicks.

**Example.** North Dakota adult name change splits into `…/adult-name-change/standard/` (any change including the last name: 5 forms, publication, 30-day wait, `.ics` deadline) and `…/adult-name-change/waiver/` (first/middle only: 4 forms, no publication or wait, no deadline). Eviction will split tenant vs. landlord the same way.

**"Linear" describes section order, not the user's path.** It is not a forward-only wizard: the whole flow is one page and users move back and forth — re-reading an info section, correcting an answer they already gave. Answers persist (PRG + the session `AnswerStore`), so revisiting is lossless. In-page wayfinding (a table of contents, section anchors, returning to the section you saved from) is therefore a first-class concern, not decoration.

**Why.** Keeps the engine simple and static, keeps corpora authorable as plain content by non-engineers (including legal reviewers), and treats routing as a human/court concern rather than engine logic.

---

## Tech Stack Decisions

| Decision           | Choice                        | Rationale                                 |
| ------------------ | ----------------------------- | ----------------------------------------- |
| **Backend**        | Django                        | Team expertise, proven at scale           |
| **Components**     | Django Cotton                 | Server-rendered, no JS framework needed   |
| **Styling**        | Tailwind CSS (standalone CLI) | Utility-first, no Node.js needed          |
| **Reactivity**     | AlpineJS (standard build)     | Lightweight, supports x-html for markdown |
| **Component Docs** | Custom `/style-guide/` page   | Django-native, living documentation       |
| **A11y Testing**   | Browser DevTools + Lighthouse | No dependencies, built into browsers      |

---

## Architecture Patterns

### Component Structure (Atomic Design)

```
templates/
├── cotton/                    # Django Cotton components
│   ├── atoms/                 # Basic elements: alert, button, chat_bubble, icon, input, link, nav_link, search_input, select, typing_indicator
│   ├── molecules/             # Combinations: chat_message, logo, search_bar, search_result, topic_card
│   └── organisms/             # Complex sections: chat_window, footer, header, hero, topic_grid
├── pages/                     # Full pages (extend base.html)
└── base.html                  # Responsive base layout
```

**Component syntax:** `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`

### Page Layout

Dashboard home with separate chat page:

```
/ (Dashboard)                    /chat/ (Chat)
┌──────────────────────┐        ┌──────────────────────┐
│ Header               │        │ Header               │
├──────────────────────┤        ├──────────────────────┤
│ Hero                 │        │ Hero (pre-chat)      │
│  How can we help?    │        │  [____search____]    │
│  [____search____]    │        ├──────────────────────┤
├──────────────────────┤        │ Chat messages        │
│ Browse by Topic      │        │ (AI streaming)       │
│ [cards grid]         │        ├──────────────────────┤
├──────────────────────┤        │ [input] [send]       │
│ Footer               │        │ (no footer)          │
└──────────────────────┘        └──────────────────────┘
```

- **Dashboard** (`/`) shows hero + topic grid + footer
- **Chat** (`/chat/`) is a full-screen chat interface (no footer, `overflow-hidden`)
- **Agent testing** (`/test/<agent_name>/`) renders chat with a specific agent

### Naming Conventions

- **Files:** `snake_case.html`
- **Cotton components:** `<c-component-name>` (kebab-case)
- **AlpineJS:** `x-data="componentName"` (camelCase)
- **CSS:** Tailwind utilities at component level

### State Flow (Django → Alpine)

Django renders initial state, Alpine handles client reactivity:

```html
<div x-data="{ expanded: false }" x-init="initWithState({{ state|safe }})">
  <!-- Alpine handles UI state, Django handles data -->
</div>
```

---

## WCAG AA Compliance

**All components must have:**

1. **Keyboard navigation** - Tab, Enter, Space, Arrows
2. **Focus indicators** - `focus:ring-2 focus:ring-offset-2`
3. **Color contrast** - 4.5:1 minimum (3:1 for large text)
4. **Touch targets** - 44x44px minimum
5. **ARIA labels** - For icon-only buttons, form associations

**Testing:** Browser DevTools (Lighthouse, axe extension) + manual testing

---

## Mobile-First Strategy

**Breakpoints:**

- Default: Mobile
- `sm:` 640px (small tablets)
- `md:` 768px (tablets)
- `lg:` 1024px (desktop)

**Key Pattern:** Single question per screen for forms

```html
<!-- Mobile: full screen question -->
<!-- Desktop: sidebar + main content -->
<div class="px-4 md:px-6 lg:max-w-2xl lg:mx-auto"></div>
```

---

## Security

- **CSP configured** - Inline handlers blocked, Alpine.js directives used
- **AlpineJS standard build** - Currently using standard build for markdown rendering (x-html). CSP build planned for production hardening.
- **django-csp** - Header management via `CSP_*` settings
- **VDP:** [free.law/vulnerability-disclosure-policy](https://free.law/vulnerability-disclosure-policy/)

---

## Key Files

| File                          | Purpose                                         |
| ----------------------------- | ----------------------------------------------- |
| `config/settings.py`          | Django + Cotton config                          |
| `static/css/main.css`         | Tailwind v4 CSS source + theme tokens           |
| `static/js/theme.js`          | Alpine theme store                              |
| `static/js/chat.js`           | Alpine chat components (homePage, chatWindow)   |
| `templates/cotton/*/`         | Component library (atoms, molecules, organisms) |
| `templates/pages/home.html`   | Dashboard with hero and topic grid              |
| `templates/pages/chat.html`   | Full-screen chat interface                      |
| `docker/django/Dockerfile`    | Multi-stage build (dev + prod)                  |
| `docker-compose.yml`          | Dev/prod profiles with PostgreSQL               |
| `docker/django/entrypoint.sh` | Container startup commands                      |

---

## Docker

### Development

```bash
cp .env.example .env
docker compose --profile dev up
# or: make docker-dev
```

- Mounts source code for hot reload
- Tailwind CSS watch mode
- PostgreSQL (pgvector) via Docker Compose service

### Production

```bash
docker compose --profile prod up
# or: make docker-prod
```

- Gunicorn WSGI server
- PostgreSQL (pgvector) with persistent volume
- Pre-built CSS (minified)
- Non-root container user

### Architecture

```
┌──────────────────────────────────────────┐
│ docker-compose.yml                       │
├──────────────────────────────────────────┤
│ Profile: dev          Profile: prod      │
│ ┌───────────┐         ┌───────────┐      │
│ │django-dev │         │django-prod│      │
│ │ runserver │         │ gunicorn  │      │
│ │ + tailwind│         │           │      │
│ └─────┬─────┘         └─────┬─────┘      │
│       └───────┐    ┌────────┘            │
│           ┌───┴────┴──┐                  │
│           │ postgres   │                  │
│           │ (pgvector) │                  │
│           └────────────┘                  │
└──────────────────────────────────────────┘
```

---

## AI Chat

The portal includes an AI chat feature using LiteLLM with OpenAI (gpt-4o-mini by default).

### Architecture

```
User Input → POST /api/chat/send/ → Django creates message
           → GET /api/chat/stream/<session_id>/ (SSE)
           → Groq API (OpenAI-compatible)
           → StreamingHttpResponse → Alpine.js updates UI
```

### Configuration

1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. Add to `.env`:

```bash
OPENAI_API_KEY=sk-...                         # Required for chat
CHAT_ENABLED=true                             # Enable/disable chat feature
CHAT_MODEL=openai/gpt-4o-mini                 # LiteLLM model string
```

### Why OpenAI via LiteLLM?

- **LiteLLM** - Unified interface for 100+ LLM providers
- **Easy to swap** - Change `CHAT_MODEL` env var to switch providers (e.g. `groq/llama-3.3-70b-versatile`)
- **No local setup** - No GPU requirements, works anywhere

---

## References

- [Django Cotton](https://django-cotton.com/)
- [AlpineJS](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [LiteLLM](https://docs.litellm.ai/) - Unified LLM API interface
- [WCAG 2.1 Quick Ref](https://www.w3.org/WAI/WCAG21/quickref/)
- [CourtListener Frontend](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
