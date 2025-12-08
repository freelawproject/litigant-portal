# Litigant Portal - Development Guide

## Quick Start

```bash
./dev.sh                    # Start Django + Vite dev servers
# Visit: http://localhost:8000/components/
```

**Other Commands:**
```bash
npm run build              # Build production assets
python manage.py shell     # Django shell
```

---

## Project Status

| Phase | Status |
|-------|--------|
| Django Foundation | Done |
| Frontend Pipeline (Vite + Tailwind + Alpine) | Done |
| Core Atoms (Button, Input, Link, Select, Icon) | Done |
| Storybook Integration | Planning |

**Current Branch:** `django-atomic`

---

## URLs (Development)

| URL | Purpose |
|-----|---------|
| http://localhost:8000/ | Home |
| http://localhost:8000/components/ | Component library |
| http://localhost:8000/style-guide/ | Design tokens |
| http://localhost:8000/admin/ | Django admin |
| http://localhost:5173/ | Vite dev server (assets) |

---

## Project Structure

```
litigant-portal/
├── config/                 # Django settings
├── portal/                 # Main Django app
├── templates/
│   ├── base.html          # Base layout
│   ├── cotton/            # Django-Cotton components
│   ├── layouts/           # Layout templates
│   └── pages/             # Page templates
├── frontend/src/
│   ├── main.js            # AlpineJS entry
│   ├── styles/            # Tailwind CSS
│   └── scripts/stores/    # Alpine stores
├── static/                # Vite build output
└── docs/                  # This folder
```

---

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Tech stack, key decisions, patterns |
| [REQUIREMENTS.md](./REQUIREMENTS.md) | Product requirements, UX principles |
| [STORYBOOK_INTEGRATION.md](./STORYBOOK_INTEGRATION.md) | Storybook implementation plan |
| [CHANGES.md](./CHANGES.md) | Changelog |
| [SECURITY.md](./SECURITY.md) | Vulnerability disclosure |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.2, Python 3.13 |
| Components | Django Cotton |
| Styling | Tailwind CSS 3.4 |
| Reactivity | AlpineJS 3.14 |
| Build | Vite 6 |
| Auth | django-allauth |
| Security | django-csp |

---

## Component Usage

```html
<!-- Button -->
<c-button variant="primary">Submit</c-button>
<c-button variant="secondary" disabled>Cancel</c-button>

<!-- Input -->
<c-input type="email" placeholder="Email" error />

<!-- Link -->
<c-link href="/dashboard" variant="primary">Dashboard</c-link>

<!-- Select -->
<c-select name="state">
  <option value="">Select...</option>
</c-select>

<!-- Icon (Heroicons) -->
{% load heroicons %}
{% heroicon "check-circle" %}
```

---

## Workflow Guidelines

- Propose changes before implementing
- One task at a time
- Keep responses concise
