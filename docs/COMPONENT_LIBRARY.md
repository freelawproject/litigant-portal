# Component Library & Testing

How LP documents, builds, and tests its UI components. The component inventory
itself lives in the repo — this page covers the approach and the workflows
around it.

---

## Approach

Our design system uses a Django-native approach:

- **Component library** - Custom page at `/style-guide/` for live demos and props docs
- **A11y testing** - Browser DevTools + manual testing (see [wcag-strategy.md](./wcag-strategy.md))
- **Viewport testing** - Browser DevTools + manual testing

This was chosen over Storybook for simplicity and to stay Django-native — no
Node.js, no JS build step.

---

## Where things live

| Thing                        | Location                                                            |
| ---------------------------- | ------------------------------------------------------------------- |
| Components (source of truth) | `litigant_portal/app/templates/cotton/{atoms,molecules,organisms}/` |
| Style guide page             | http://portal.localhost/style-guide/                                |
| Style guide template         | `litigant_portal/app/templates/pages/style_guide.html`              |
| Style guide view             | `litigant_portal/app/views/pages.py::style_guide()`                 |
| Theme tokens                 | `@theme { }` blocks in `litigant_portal/app/src/main.css`           |
| Component CSS classes        | `@layer components` in `litigant_portal/app/src/main.css`           |

Component syntax: `<c-atoms.button>`, `<c-molecules.logo>`, `<c-organisms.header>`.
The current inventory is the directory listing plus the tree in
[CLAUDE.md](../CLAUDE.md) — the style guide page shows each component live.

---

## Component discipline

Don't freehand new UI. Before creating anything:

1. Check existing components in `templates/cotton/`
2. Check theme tokens in `src/main.css`
3. Compose from existing components first

Only create a new component when no combination of existing ones works
(org rule — see CLAUDE.md for the atomic design check that applies to every
template change).

## Adding a new component

1. Create the Cotton component at the right atomic level:
   - Atoms: basic elements (one HTML concept)
   - Molecules: combinations of atoms
   - Organisms: complex sections
2. Add CSS to `@layer components` in `main.css` only if utilities can't express it
3. Add a section to `style_guide.html`: description, live demo with variants,
   props table, collapsible code example (copy the structure of an existing
   section)
4. Load the `django-templates` skill conventions before writing template markup

---

## A11y Testing

Browser-based, no extra dependencies:

1. **Chrome DevTools Lighthouse** - Built-in accessibility audit
2. **axe DevTools extension** - [Chrome](https://chrome.google.com/webstore/detail/axe-devtools/lhdoppojpmngadmnindnejefpokejbdd) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/axe-devtools/)
3. **Manual testing** - Keyboard navigation, screen reader

Per-component checklist:

- [ ] Color contrast 4.5:1 minimum (3:1 for large text)
- [ ] Touch targets 44x44px minimum
- [ ] Keyboard navigable (Tab, Enter, Space)
- [ ] Focus indicators visible
- [ ] ARIA labels where needed
- [ ] Screen reader tested

The full audit strategy (WCAG 2.2 AA, org floor) is in
[wcag-strategy.md](./wcag-strategy.md).

---

## Viewport Testing

Test components at these breakpoints (DevTools device toolbar,
Ctrl/Cmd+Shift+M):

| Device         | Width   | Notes           |
| -------------- | ------- | --------------- |
| Small phone    | 375px   | iPhone SE       |
| Standard phone | 390px   | iPhone 12/13/14 |
| Large phone    | 428px   | iPhone Pro Max  |
| Tablet         | 768px   | iPad            |
| Desktop        | 1024px+ | Laptop/Desktop  |

---

## Design System Source

Tailwind config and CSS patterns are adapted from
[CourtListener](https://github.com/freelawproject/courtlistener):

- Color palette (greyscale, primary coral/red, brand purple)
- Typography (Inter, Cooper Hewitt fonts)
- Spacing scale and component patterns

Tailwind v4 uses CSS-based configuration — theme tokens live in `@theme { }`
blocks in `main.css`, no `tailwind.config.js`. Build with `make css`
(or `make css-watch` during development; the Docker dev environment watches
automatically).
