# Litigant Portal - Development Guide

## Quick Start

```bash
./dev.sh                    # Start Django + Tailwind CSS watch
# Visit: http://localhost:8000/components/
```

**Other Commands:**

```bash
tailwindcss -i static/css/main.css -o static/css/main.built.css --minify  # Build production CSS
tailwindcss -i static/css/main.css -o static/css/main.built.css --watch   # Watch CSS
python manage.py shell                                                      # Django shell
```

**Requirements:** Python 3.13+, Tailwind CSS (`brew install tailwindcss`)

---

## Project Status

| Phase                                          | Status |
| ---------------------------------------------- | ------ |
| Django Foundation                              | Done   |
| Frontend Pipeline (Tailwind CLI + Alpine CDN)  | Done   |
| Core Atoms (Button, Input, Link, Select, Icon) | Done   |
| Component Library Page                         | Done   |
| A11y Testing                                   | Next   |

**Branch:** `django-atomic`

---

## URLs (Development)

| URL                                | Purpose           |
| ---------------------------------- | ----------------- |
| http://localhost:8000/             | Home              |
| http://localhost:8000/components/  | Component library |
| http://localhost:8000/style-guide/ | Style guide       |
| http://localhost:8000/admin/       | Django admin      |

---

## Project Structure

```
litigant-portal/
├── config/                 # Django settings
├── portal/                 # Main Django app
├── templates/
│   ├── base.html          # Base layout (responsive)
│   ├── cotton/            # Django-Cotton components (Atomic Design)
│   │   ├── atoms/         # Basic elements (button, input, link, etc.)
│   │   ├── molecules/     # Combinations (logo, search_bar, topic_card)
│   │   └── organisms/     # Complex sections (header, footer, hero)
│   └── pages/             # Page templates
├── static/
│   ├── css/
│   │   ├── main.css       # Tailwind source
│   │   └── main.built.css # Tailwind output (gitignored)
│   ├── images/            # Static images (logo.svg)
│   └── js/
│       └── theme.js       # Alpine theme store
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

| Layer      | Technology                                              |
| ---------- | ------------------------------------------------------- |
| Backend    | Django 6.0, Python 3.13                                 |
| Components | Django Cotton                                           |
| Styling    | Tailwind CSS 4.x (Homebrew: `brew install tailwindcss`) |
| Reactivity | AlpineJS 3.15.1 (CDN)                                   |
| Auth       | django-allauth                                          |
| Security   | Django built-in CSP                                     |

**No Node.js required** - Tailwind via Homebrew, Alpine via CDN.

---

## Component Usage

```html
<!-- Button -->
<c-button variant="primary">Submit</c-button>
<c-button variant="outline">Cancel</c-button>
<c-button variant="danger" disabled>Delete</c-button>

<!-- Input -->
<c-input type="email" placeholder="Email" error />

<!-- Link -->
<c-link href="/dashboard" variant="primary">Dashboard</c-link>
<c-link href="https://example.com" target="_blank" external_icon
  >External</c-link
>

<!-- Select -->
<c-select name="state">
  <option value="">Select...</option>
</c-select>

<!-- Icon (Heroicons) -->
<c-icon name="check-circle" class="w-6 h-6" />
<c-icon name="check-circle" style="solid" class="w-6 h-6 text-green-600" />
```

---

## Design System

Colors and patterns adapted from CourtListener:

- **Primary:** Coral/red (`primary-600: #B5362D`)
- **Greyscale:** Warm greys (`greyscale-900: #1C1814`)
- **Brand:** Purple accents (`brand-600: #7F56D9`)

See `/components/` for live examples and full documentation.

---

## Workflow Guidelines

- Propose changes before implementing
- One task at a time
- Keep responses concise
