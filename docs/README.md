# Litigant Portal - Development Guide

## Quick Start

```bash
cp .env.example .env        # Add your GROQ_API_KEY
make docker-dev             # Start dev environment
# Visit: http://portal.localhost:8000/style-guide/
```

**Other Commands:**

```bash
make docker-shell           # Shell into container
make docker-down            # Stop containers
make test                   # Run tests
```

**Requirements:** Docker

---

## Project Status

| Phase                                           | Status |
| ----------------------------------------------- | ------ |
| Django Foundation                               | Done   |
| Frontend Pipeline (Tailwind CLI + Alpine local) | Done   |
| Core Atoms (Button, Input, Link, Select, Icon)  | Done   |
| Component Library Page                          | Done   |
| Auth (Login/Signup/Logout)                      | Done   |
| AI Chat with Groq                               | Done   |
| A11y Testing                                    | Next   |

---

## URLs (Development)

| URL                                       | Purpose                   |
| ----------------------------------------- | ------------------------- |
| http://portal.localhost:8000/             | Dashboard (hero + topics) |
| http://portal.localhost:8000/chat/        | AI chat interface         |
| http://portal.localhost:8000/style-guide/ | Component library / guide |
| http://portal.localhost:8000/admin/       | Django admin              |

---

## Project Structure

```
litigant-portal/
├── config/                 # Django settings
├── portal/                 # Main Django app (views, models, forms)
├── chat/                   # AI chat app (providers, services, agents)
├── templates/
│   ├── base.html          # Base layout (responsive)
│   ├── cotton/            # Django-Cotton components (Atomic Design)
│   │   ├── atoms/         # Basic elements (button, input, link, etc.)
│   │   ├── molecules/     # Combinations (logo, search_bar, topic_card)
│   │   └── organisms/     # Complex sections (header, footer, hero)
│   └── pages/             # Page templates (home, chat, profile, etc.)
├── static/
│   ├── css/
│   │   ├── main.css       # Tailwind source
│   │   └── main.built.css # Tailwind output (gitignored)
│   ├── images/            # Static images (logo.svg)
│   └── js/
│       ├── theme.js       # Alpine theme store
│       └── chat.js        # Alpine chat component
└── docs/                  # This folder
```

---

## Documentation Index

| Doc                                            | Purpose                             |
| ---------------------------------------------- | ----------------------------------- |
| [ARCHITECTURE.md](./ARCHITECTURE.md)           | Tech stack, key decisions, patterns |
| [REQUIREMENTS.md](./REQUIREMENTS.md)           | Product requirements, UX principles |
| [COMPONENT_LIBRARY.md](./COMPONENT_LIBRARY.md) | Component library & testing guide   |
| [CHANGES.md](./CHANGES.md)                     | Changelog                           |
| [SECURITY.md](./SECURITY.md)                   | Vulnerability disclosure            |

---

## Tech Stack

| Layer      | Technology                               |
| ---------- | ---------------------------------------- |
| Backend    | Django 5.2 LTS, Python 3.13              |
| Components | Django Cotton                            |
| Styling    | Tailwind CSS 4.x (standalone CLI)        |
| Reactivity | Alpine.js 3.14.9 (local, standard build) |
| Auth       | django-allauth                           |
| AI Chat    | Groq (llama-3.3-70b-versatile)           |
| Security   | django-csp                               |
| Deployment | Fly.io (QA), GitHub Pages (static demo)  |

**No Node.js required** - Tailwind via standalone CLI, Alpine.js local files.

---

## Component Usage

```html
<!-- Button -->
<c-atoms.button variant="primary">Submit</c-atoms.button>
<c-atoms.button variant="outline">Cancel</c-atoms.button>
<c-atoms.button variant="danger" disabled>Delete</c-atoms.button>

<!-- Input -->
<c-atoms.input type="email" placeholder="Email" error />

<!-- Form Field (label + input + errors) -->
<c-molecules.form-field
  label="Email"
  type="email"
  name="email"
  id="id_email"
  required
/>

<!-- Link -->
<c-atoms.link href="/dashboard" variant="primary">Dashboard</c-atoms.link>
<c-atoms.link href="https://example.com" target="_blank" external_icon>
  External
</c-atoms.link>

<!-- Select -->
<c-atoms.select name="state">
  <option value="">Select...</option>
</c-atoms.select>

<!-- Icon (Heroicons) -->
<c-atoms.icon name="check-circle" class="w-6 h-6" />
<c-atoms.icon
  name="check-circle"
  style="solid"
  class="w-6 h-6 text-green-600"
/>

<!-- Checkbox -->
<c-atoms.checkbox name="remember" id="remember" label="Remember me" />
```

---

## Design System

Colors and patterns adapted from CourtListener:

- **Primary:** Coral/red (`primary-600: #B5362D`)
- **Greyscale:** Warm greys (`greyscale-900: #1C1814`)
- **Brand:** Purple accents (`brand-600: #7F56D9`)

See `/style-guide/` for live examples and full documentation.

---

## Deployment

**GitHub Pages (Static Demo):**

Live site: https://freelawproject.github.io/litigant-portal/

Deploys automatically on push to `main` via GitHub Actions. Uses `django-distill` to pre-render pages as static HTML.

```bash
# Generate static site locally
uv run python manage.py collectstatic --noinput
uv run python manage.py distill-local dist --force
```

---

## Workflow Guidelines

- Propose changes before implementing
- One task at a time
- Keep responses concise
