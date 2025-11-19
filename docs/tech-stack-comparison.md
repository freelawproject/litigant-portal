# Litigant Portal: Tech Stack Comparison

**Date:** November 18, 2025
**Author:** Mitch (Project Lead)
**Purpose:** Comparative analysis of SvelteKit vs Django/Cotton stacks for the Litigant Portal project

---

## Executive Summary

This document compares two proposed tech stacks for the Litigant Portal:

1. **SvelteKit Stack** (lp-svelte) - Modern frontend framework with Python API backend
2. **Django/Cotton Stack** (litigant-portal) - Traditional Django templating with Cotton components and AlpineJS

**Recommendation:** The SvelteKit stack is better suited for this project due to its frontend-heavy requirements, white-label architecture needs, mobile-first approach, and alignment with project leadership expertise.

---

## Tech Stack Details

### SvelteKit Stack (lp-svelte)

**Frontend:**

- **Framework:** SvelteKit 2.x (latest)
- **Language:** TypeScript
- **Styling:** UnoCSS (utility-first, highly customizable)
- **Component Library:** Atomic Design pattern with Storybook
- **Icons:** Lucide Icons (@lucide/svelte)
- **Testing:** Vitest (unit), Playwright (e2e), Storybook (visual/a11y)
- **Build Tool:** Vite 7.x

**Backend (Proposed):**

- Python FastAPI or Django REST Framework
- PostgreSQL
- Authentication/Authorization APIs
- Document processing services

**Key Features:**

- Built-in CSP (Content Security Policy) configuration
- TypeScript type safety
- Hot module replacement (HMR) for fast development
- Static site generation (SSG) or server-side rendering (SSR) options
- PWA support via service workers
- Adapter-based deployment (static, Node, serverless, edge)

### Django/Cotton Stack (litigant-portal)

**Backend:**

- **Framework:** Django (Python 3.13+)
- **Templates:** Django Cotton components
- **JavaScript:** AlpineJS for interactivity
- **Styling:** TailwindCSS (likely, based on CourtListener reference)
- **Testing:** pytest, Django test framework

**Key Features:**

- Leverages existing team Django expertise
- Monolithic architecture (frontend + backend in one repo)
- Server-side rendering
- Django ORM for database access
- Django admin for content management

---

## Requirements Analysis

Based on the requirements document, the Litigant Portal is characterized by:

### Frontend-Heavy Requirements (70-80% of complexity)

**Must Have:**

- Dynamic personalized dashboard (court dates, next steps, reminders)
- Guided form-filling interviews with save/resume
- Case type selection with AI assistance
- Document type selection with plain language overlays
- Party role selection with explanations
- Real-time notifications (court → portal → user via email/SMS)
- WCAG accessibility compliance
- Mobile responsive design

**Should Have:**

- User login + persistent form state
- E-filing integration
- Fee waiver guided interviews
- Integration with A2J Author, HotDocs, DocAssemble (XML/JSON parsing)
- Credit card/ACH payment processing
- Case search and attachment
- Multi-case history view

**Could Have:**

- SMS reminders tied to case deadlines
- OCR for uploaded documents
- AI-curated contextual help
- Multi-language support
- Multimedia file uploads with in-browser playback
- File format conversion

### Backend Requirements (20-30% of complexity)

- User authentication and authorization
- Document storage and retrieval
- Court API integrations (e-filing)
- Payment processing
- Notification system
- Role-based access control (litigant, clerk, judge, IT)

### White-Label Requirements

- Theme/design customization per court
- Modular architecture (user portal, court portal, EFM can be used independently)
- Court-specific configurations (fee structures, document requirements, workflows)

---

## Comparative Analysis: Pros & Cons

### SvelteKit Stack

#### Pros

**1. Modern Frontend Architecture**

- Svelte compiles to highly optimized vanilla JavaScript (no runtime framework overhead)
- Excellent performance on mobile devices (critical for self-represented litigants)
- Bundle sizes typically 30-70% smaller than React/Vue
- Built-in reactivity without virtual DOM overhead

**2. White-Label/Theming Excellence**

- UnoCSS supports dynamic theming via CSS custom properties at runtime
- No rebuild required to switch themes - can be configured per-court via API
- Atomic design system with Storybook enables isolated component development
- Components can be themed independently and composed into court-specific UIs

**3. Form Handling & State Management**

- Svelte stores provide elegant, reactive state management for complex forms
- Built-in two-way binding reduces boilerplate for guided interviews
- Easy to implement save/resume functionality with localStorage or API persistence
- Conditional logic and field dependencies are straightforward with reactive statements

**4. Component Development Velocity**

- Already has atomic design system started (Button, Input, Select, Link, Icon)
- Storybook provides isolated component development, testing, and documentation
- Accessibility testing integrated via @storybook/addon-a11y
- Component reusability across white-label deployments is maximized

**5. Testing Infrastructure**

- Vitest for fast unit tests with browser mode
- Playwright for e2e testing (already configured)
- Storybook for visual regression and accessibility testing
- TypeScript provides compile-time error catching

**6. Mobile & PWA Capabilities**

- SvelteKit has first-class PWA support via service workers
- Offline-first architecture is straightforward to implement
- Static asset generation for CDN deployment
- Progressive enhancement by default

**7. Integration with Document Assembly Tools**

- A2J Author, HotDocs, DocAssemble all output XML/JSON answer files
- Client-side parsing and manipulation is natural in TypeScript
- Can embed guided interview iframes and communicate via postMessage
- Real-time form validation and conditional logic without server round-trips

**8. API-First Architecture**

- Frontend is completely decoupled from backend
- Python backend (FastAPI/Django REST) can focus purely on business logic
- Enables modular architecture required by specs (user portal, court portal, EFM as separate services)
- Different teams can work on frontend/backend independently

**9. Deployment Flexibility**

- Can deploy as static files to CDN (lowest cost, highest performance)
- Can use edge functions for dynamic server-side rendering
- Can deploy to Node server for traditional hosting
- Scales horizontally without server management (when using static adapter)

**10. Developer Experience**

- You (project lead) have SvelteKit expertise - can mentor team effectively
- Hot module replacement makes development fast
- TypeScript provides safety and better IDE support
- Modern tooling ecosystem (Vite, Vitest, Playwright, Storybook)

**11. Performance for Target Users**

- Self-represented litigants may be on low-bandwidth mobile connections
- Svelte's small bundle sizes and no-runtime overhead are ideal
- Lazy loading and code splitting are built-in
- Can serve from CDN for global low-latency access

**12. Future-Proof Technology**

- Svelte 5 (runes) represents cutting-edge reactive programming
- TypeScript is industry standard
- Skills are transferable to other modern web projects
- Active community and ecosystem growth

#### Cons

**1. Team Learning Curve**

- Team has Django/Python expertise, not SvelteKit
- Will need to learn TypeScript, Svelte syntax, and modern frontend tooling
- Two separate deployments (frontend + backend API) instead of monolith

**2. Backend API Required**

- Must build RESTful or GraphQL API layer
- Additional architecture complexity vs. Django views
- Need to handle CORS, authentication tokens, API versioning

**3. Initial Setup Time**

- Two codebases to manage (frontend + backend)
- CI/CD pipeline needs to handle both deployments
- Coordination required between frontend and backend releases

**4. SSR Hosting Complexity** (if not using static adapter)

- Requires Node.js hosting if using SSR
- More complex than traditional Django deployment if not going static

**5. Less Django Admin Integration**

- Can't use Django admin directly for content management
- Would need to build admin UI separately or expose Django REST admin

---

### Django/Cotton Stack

#### Pros

**1. Team Expertise**

- Team has deep Django/Python experience
- Familiar with Django patterns, ORM, admin, testing
- Can leverage existing CourtListener knowledge

**2. Monolithic Simplicity**

- Single codebase, single deployment
- Easier to reason about data flow (no API boundary)
- Django admin provides out-of-box content management

**3. Backend Integration**

- Views have direct access to ORM and business logic
- No need to design API contracts
- Session management is built-in and battle-tested

**4. Rapid Prototyping** (for simple apps)

- Django scaffolding can generate CRUD quickly
- Forms can be auto-generated from models
- Less initial architectural decisions required

**5. Python Ecosystem**

- Document processing (PDF generation, OCR) can be done server-side in Python
- No language context switching for full-stack development
- Can leverage Python AI/ML libraries directly

#### Cons

**1. White-Label Architecture Challenges**

- Dynamic theming requires either:
  - Rebuilding/redeploying for each court's theme, OR
  - Complex runtime CSS generation with Django templates, OR
  - Still needing significant client-side JavaScript for theme switching
- Component reusability is limited compared to modern component libraries
- Cotton is less mature than established frontend frameworks

**2. Frontend Interactivity Limitations**

- AlpineJS is lightweight but not designed for complex application state
- Multi-step guided interviews with save/resume require careful session management
- Mixing server-rendered HTML with client-side state can be error-prone
- Real-time features require Django Channels/WebSockets (additional complexity)

**3. Mobile & PWA Limitations**

- Django is server-centric, not optimized for PWA patterns
- Service worker implementation requires custom JavaScript infrastructure
- Offline-first architecture is complex to implement with server-rendered apps
- Page transitions are full reloads (less app-like experience)

**4. Form Complexity**

- Complex conditional form logic requires JavaScript anyway
- Save/resume functionality needs careful session/database state management
- Client-side validation requires duplicate logic (Python validators + JavaScript)
- A2J Author/HotDocs/DocAssemble integration still requires significant JavaScript

**5. Component Testing**

- Django template testing is less robust than modern component testing
- AlpineJS logic is harder to unit test than framework components
- No equivalent to Storybook for isolated component development
- Visual regression testing is less standardized

**6. Performance Concerns**

- Server-side rendering means every interaction can require a server round-trip
- TailwindCSS + AlpineJS + Django templates can result in larger HTML payloads
- Mobile users on slow connections may experience sluggishness
- Caching strategies are more complex than static CDN hosting

**7. Deployment & Scaling**

- Requires traditional server/container hosting (can't use CDN for static files)
- Horizontal scaling requires load balancers, sticky sessions for stateful apps
- More infrastructure overhead than static or serverless deployments

**8. Modularity Requirements**

- Requirements explicitly state "User portal/EFM/Court Management Portal can all be used interchangeably/separately"
- Monolithic Django app makes it harder to achieve this modularity
- Would likely need to extract API layer anyway for inter-service communication

**9. TypeScript & Type Safety**

- No compile-time type checking for templates or JavaScript
- AlpineJS is untyped, making refactoring riskier
- Python typing doesn't extend to frontend logic

**10. Developer Experience Gap**

- Project lead (you) has SvelteKit expertise, not Cotton/AlpineJS
- Team would need to learn Cotton patterns (less transferable skill)
- Hot reloading is less sophisticated than Vite HMR
- Debugging Django templates + AlpineJS interactions can be frustrating

**11. Integration with Modern Tooling**

- No native Storybook integration for Cotton components
- E2E testing requires Django test client + Playwright (more setup)
- Accessibility testing tools are less integrated

**12. Frontend-Backend Coupling**

- Templates are tightly coupled to Django views
- Changes to UI often require backend changes (Python code, URL routing, views)
- Harder for frontend and backend developers to work independently
- API-first architecture (required by modularity specs) is not natural fit

---

## Head-to-Head: Key Decision Factors

| Factor                            | SvelteKit                                 | Django/Cotton                                  | Winner        |
| --------------------------------- | ----------------------------------------- | ---------------------------------------------- | ------------- |
| **White-label theming**           | Runtime CSS custom properties, no rebuild | Requires rebuild or complex runtime generation | **SvelteKit** |
| **Mobile performance**            | Tiny bundles, no runtime overhead         | Larger payloads, full page reloads             | **SvelteKit** |
| **Guided interview complexity**   | Reactive stores, client-side state        | Server sessions + AlpineJS patches             | **SvelteKit** |
| **PWA capabilities**              | First-class support, service workers      | Requires custom implementation                 | **SvelteKit** |
| **Component reusability**         | Atomic design + Storybook                 | Cotton components (less mature)                | **SvelteKit** |
| **Modularity (per requirements)** | API-first by design                       | Monolith requires refactoring                  | **SvelteKit** |
| **Team expertise**                | Requires learning                         | Leverages existing skills                      | **Django**    |
| **Initial velocity**              | Slower (two codebases)                    | Faster (monolith scaffolding)                  | **Django**    |
| **Long-term maintainability**     | Decoupled, testable, type-safe            | Coupled templates, untyped JS                  | **SvelteKit** |
| **Deployment cost**               | CDN static hosting ($$)                   | Server/container hosting ($$$)                 | **SvelteKit** |
| **Project lead expertise**        | You have SvelteKit skills                 | You'd learn Cotton/Alpine                      | **SvelteKit** |
| **Testing infrastructure**        | Vitest, Playwright, Storybook, a11y       | Django tests + manual testing                  | **SvelteKit** |

**Score: SvelteKit 10, Django 2**
