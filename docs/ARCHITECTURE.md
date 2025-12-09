# Litigant Portal - Architecture

## Vision

Democratize access to justice by empowering self-represented litigants with AI-augmented legal guidance, education, and document preparation tools.

**Core Principles:**

- Global by design (i18n from the start)
- WCAG AA accessibility as requirement
- Mobile-first (users on older phones)
- Human-centered AI (augments, not replaces)

---

## Tech Stack Decisions

| Decision           | Choice                             | Rationale                               |
| ------------------ | ---------------------------------- | --------------------------------------- |
| **Backend**        | Django                             | Team expertise, proven at scale         |
| **Components**     | Django Cotton                      | Server-rendered, no JS framework needed |
| **Styling**        | Tailwind CSS                       | Utility-first, mobile-responsive        |
| **Reactivity**     | AlpineJS                           | Lightweight (15KB), CSP-safe            |
| **Build**          | Vite                               | Fast HMR, simple config                 |
| **Component Docs** | Storybook + django-pattern-library | A11y testing, viewport testing          |

---

## Architecture Patterns

### Component Structure (Atomic Design)

```
templates/
├── cotton/           # Atoms: button, input, link, select, icon
├── molecules/        # Combinations: form_field, card, alert
├── organisms/        # Complex: header, single_question_form
├── layouts/          # Page layouts
└── pages/            # Full pages
```

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

**Testing:** Storybook addon-a11y with axe-core

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

- **CSP configured** - No unsafe-eval/inline needed
- **AlpineJS 3** - CSP-safe by default
- **django-csp** - Header management
- **VDP:** [free.law/vulnerability-disclosure-policy](https://free.law/vulnerability-disclosure-policy/)

---

## Key Files

| File                      | Purpose                       |
| ------------------------- | ----------------------------- |
| `config/settings.py`      | Django + Cotton + Vite config |
| `tailwind.config.js`      | Design tokens, colors, fonts  |
| `frontend/src/main.js`    | AlpineJS entry + stores       |
| `templates/cotton/*.html` | Component library             |

---

## References

- [Django Cotton](https://django-cotton.com/)
- [AlpineJS](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [WCAG 2.1 Quick Ref](https://www.w3.org/WAI/WCAG21/quickref/)
- [CourtListener Frontend](https://github.com/freelawproject/courtlistener/wiki/New-Frontend-Architecture)
