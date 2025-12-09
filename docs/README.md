# Litigant Portal - Development Guide

## Quick Start

```bash
./dev.sh                    # Start Django + Tailwind CSS watch
# Visit: http://localhost:8000/pattern-library/
```

**Other Commands:**

```bash
npm run build:css          # Build production CSS (minified)
npm run watch:css          # Watch CSS for changes
python manage.py shell     # Django shell
```

---

## Project Status

| Phase                                          | Status                                                                |
| ---------------------------------------------- | --------------------------------------------------------------------- |
| Django Foundation                              | Done                                                                  |
| Frontend Pipeline (Tailwind CLI + Alpine CDN)  | Done                                                                  |
| Core Atoms (Button, Input, Link, Select, Icon) | Done                                                                  |
| Storybook Integration                          | **Next** - see [STORYBOOK_INTEGRATION.md](./STORYBOOK_INTEGRATION.md) |

**Branch:** `django-atomic`

---

## URLs (Development)

| URL                                    | Purpose         |
| -------------------------------------- | --------------- |
| http://localhost:8000/                 | Home            |
| http://localhost:8000/pattern-library/ | Pattern library |
| http://localhost:8000/admin/           | Django admin    |

---

## Project Structure

```
litigant-portal/
├── config/                 # Django settings
├── portal/                 # Main Django app
├── templates/
│   ├── base.html          # Base layout
│   ├── cotton/            # Django-Cotton components
│   ├── patterns/          # Pattern library wrappers
│   ├── layouts/           # Layout templates
│   └── pages/             # Page templates
├── static/
│   ├── css/
│   │   ├── main.css       # Tailwind source
│   │   └── main.built.css # Tailwind output
│   └── js/
│       └── theme.js       # Alpine theme store
└── docs/                  # This folder
```

---

## Documentation Index

| Doc                                                    | Purpose                             |
| ------------------------------------------------------ | ----------------------------------- |
| [ARCHITECTURE.md](./ARCHITECTURE.md)                   | Tech stack, key decisions, patterns |
| [REQUIREMENTS.md](./REQUIREMENTS.md)                   | Product requirements, UX principles |
| [STORYBOOK_INTEGRATION.md](./STORYBOOK_INTEGRATION.md) | Storybook implementation plan       |
| [CHANGES.md](./CHANGES.md)                             | Changelog                           |
| [SECURITY.md](./SECURITY.md)                           | Vulnerability disclosure            |

---

## Tech Stack

| Layer      | Technology              |
| ---------- | ----------------------- |
| Backend    | Django 5.2, Python 3.13 |
| Components | Django Cotton           |
| Styling    | Tailwind CSS 3.4 (CLI)  |
| Reactivity | AlpineJS 3.14 (CDN)     |
| Auth       | django-allauth          |
| Security   | django-csp              |

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
{% load heroicons %} {% heroicon "check-circle" %}
```

---

## Workflow Guidelines

- Propose changes before implementing
- One task at a time
- Keep responses concise
