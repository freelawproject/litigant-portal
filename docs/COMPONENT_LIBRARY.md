# Component Library & Testing

**Branch:** `django-atomic`

---

## Current Status

- [x] Build simplification (Tailwind standalone CLI + Alpine.js local files)
- [x] Node.js removed - zero JS build dependencies
- [x] Tailwind v4 CSS-based config (no tailwind.config.js needed)
- [x] CourtListener color scheme adopted
- [x] Custom component library page at `/style-guide/`
- [x] Cotton components documented (Button, Input, Select, Link, Icon, Alerts)
- [x] A11y testing via browser DevTools (Lighthouse, axe extension)

---

## Overview

Our design system uses a Django-native approach:

- **Component Library** - Custom page at `/style-guide/` for developer documentation
- **A11y Testing** - axe-core via npm scripts (roll-our-own, not Storybook)
- **Viewport Testing** - Browser DevTools + manual testing

This approach was chosen over Storybook for simplicity and to stay Django-native.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Component Library Page                      │
│  /style-guide/ - Live demos, props docs, code examples  │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 Django Cotton (Atomic Design)           │
│  templates/cotton/{atoms,molecules,organisms}/*.html    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Tailwind CSS + Alpine.js                   │
│  static/css/main.css + static/js/alpine.min.js          │
└─────────────────────────────────────────────────────────┘
```

---

## Key Decisions

| Decision            | Choice                                | Rationale                          |
| ------------------- | ------------------------------------- | ---------------------------------- |
| **Component docs**  | Custom Django page                    | Django-native, full control        |
| **A11y testing**    | axe-core npm scripts                  | Lightweight, no Storybook overhead |
| **Pattern library** | None (removed django-pattern-library) | Custom page is sufficient          |
| **Storybook**       | Removed from plan                     | Overkill for current needs         |

---

## Component Library

### URL

- Development: http://portal.localhost:8000/style-guide/
- Template: `templates/pages/style_guide.html`
- View: `portal/views.py::style_guide()`

### Structure

Each component section includes:

- **Description** - What the component does, accessibility notes
- **Demo** - Live rendered component with variants
- **Props table** - All available props with types and defaults
- **Slots table** - Named slots (if applicable)
- **Code example** - Collapsible code snippet

### Adding a New Component

1. Create Cotton component in the appropriate atomic level:
   - Atoms: `templates/cotton/atoms/my_component.html` (basic elements)
   - Molecules: `templates/cotton/molecules/my_component.html` (combinations of atoms)
   - Organisms: `templates/cotton/organisms/my_component.html` (complex sections)
2. Add CSS classes to `static/css/main.css` if needed
3. Add section to `templates/pages/style_guide.html`:

```html
{# ========== MY COMPONENT ========== #}
<section id="my-component" class="mb-16 pt-4 border-t-2 border-greyscale-200">
  <h2 class="mb-4">My Component</h2>
  <p class="text-greyscale-600 mb-6">Description here.</p>

  {# Demo #}
  <h4 class="mb-3">Demo</h4>
  <div class="mb-6">
    <c-my-component>Content</c-my-component>
  </div>

  {# Props #}
  <h4 class="mt-8">Props</h4>
  <div class="bg-greyscale-100 rounded-xl p-4 my-3">
    <div class="flex flex-col md:flex-row border-b border-greyscale-200">
      <span class="p-2.5 md:w-48 font-medium"><code>prop_name</code></span>
      <span class="p-2.5">Description. Default: "value"</span>
    </div>
  </div>

  {# Code #}
  <details class="mt-4">
    <summary class="cursor-pointer text-sm font-medium text-greyscale-600">
      Show code
    </summary>
    <pre
      class="mt-2 bg-greyscale-50 border border-greyscale-300 rounded-[10px] p-4"
    ><code>&lt;c-my-component&gt;Content&lt;/c-my-component&gt;</code></pre>
  </details>
</section>
```

4. Add navigation link to sidebar

---

## Current Components

### Atoms

| Component        | File                          | Description                                                                           |
| ---------------- | ----------------------------- | ------------------------------------------------------------------------------------- |
| Button           | `atoms/button.html`           | Primary, outline, dark, ghost, danger variants                                        |
| Checkbox         | `atoms/checkbox.html`         | Checkbox with optional label                                                          |
| Input            | `atoms/input.html`            | Text inputs with error/success states                                                 |
| Search Input     | `atoms/search_input.html`     | Search input with icon, large touch target                                            |
| Select           | `atoms/select.html`           | Dropdown with custom styling                                                          |
| Link             | `atoms/link.html`             | Styled links with external icon option                                                |
| Icon             | `atoms/icon.html`             | Heroicons v2 wrapper (`magnifying-glass`, `x-mark`, `exclamation-triangle`, `bars-3`) |
| Alert            | `atoms/alert.html`            | Info, success, warning, danger alert styles                                           |
| Chat Bubble      | `atoms/chat_bubble.html`      | Chat message bubble with role-based styling (user/assistant)                          |
| Typing Indicator | `atoms/typing_indicator.html` | Animated typing dots for streaming responses                                          |
| Nav Link         | `atoms/nav_link.html`         | Navigation link with active state styling                                             |

### Molecules

| Component     | File                           | Description                                 |
| ------------- | ------------------------------ | ------------------------------------------- |
| Form Field    | `molecules/form_field.html`    | Label + input + help text + error display   |
| Logo          | `molecules/logo.html`          | Portal logo/branding, links to home         |
| Search Bar    | `molecules/search_bar.html`    | Search input + submit button combo          |
| Topic Card    | `molecules/topic_card.html`    | Tappable card with icon, title, description |
| Chat Message  | `molecules/chat_message.html`  | Full chat message with bubble and metadata  |
| Search Result | `molecules/search_result.html` | Search result card with title and excerpt   |
| User Menu     | `molecules/user_menu.html`     | Header auth badge/dropdown                  |

### Organisms

| Component   | File                         | Description                             |
| ----------- | ---------------------------- | --------------------------------------- |
| Header      | `organisms/header.html`      | Sticky header with logo + menu toggle   |
| Hero        | `organisms/hero.html`        | Heading + subheading + search bar       |
| Topic Grid  | `organisms/topic_grid.html`  | Responsive grid of topic cards          |
| Footer      | `organisms/footer.html`      | Footer with nav links                   |
| Chat Window | `organisms/chat_window.html` | Complete chat interface with SSE stream |

### CSS Component Classes

Defined in `static/css/main.css`:

```css
/* Buttons */
.btn-primary, .btn-outline, .btn-dark, .btn-ghost, .btn-danger
.btn-xl, .btn-sm

/* Inputs */
.input, .input-error, .input-success

/* Selects */
.select-wrapper, .select, .select-icon
.select-wrapper-error, .select-wrapper-disabled

/* Links */
.link, .link-default, .link-primary, .link-secondary, .link-unstyled

/* Alerts */
.alert, .alert-info, .alert-success, .alert-warning, .alert-danger

/* Layout */
.container-desktop, .container-mobile, .capped-width
```

---

## A11y Testing

### Approach

Browser-based A11y testing (no Node.js required):

1. **Chrome DevTools Lighthouse** - Built-in accessibility audit
2. **axe DevTools Extension** - [Chrome](https://chrome.google.com/webstore/detail/axe-devtools/lhdoppojpmngadmnindnejefpokejbdd) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/axe-devtools/)
3. **Manual testing** - Keyboard navigation, screen reader

### Manual Checklist

For each component:

- [ ] Color contrast 4.5:1 minimum (use browser DevTools)
- [ ] Touch targets 44x44px minimum
- [ ] Keyboard navigable (Tab, Enter, Space)
- [ ] Focus indicators visible
- [ ] ARIA labels where needed
- [ ] Screen reader tested

---

## Viewport Testing

### Manual Testing Sizes

Test components at these breakpoints:

| Device         | Width   | Notes           |
| -------------- | ------- | --------------- |
| Small phone    | 375px   | iPhone SE       |
| Standard phone | 390px   | iPhone 12/13/14 |
| Large phone    | 428px   | iPhone Pro Max  |
| Tablet         | 768px   | iPad            |
| Desktop        | 1024px+ | Laptop/Desktop  |

### Browser DevTools

1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M / Cmd+Shift+M)
3. Select device preset or enter custom dimensions
4. Test component at each size

---

## File Structure

```
litigant-portal/
├── static/
│   ├── css/
│   │   ├── main.css              # Tailwind source
│   │   └── main.built.css        # Generated CSS (gitignored)
│   ├── images/
│   │   └── logo.svg              # Site logo
│   └── js/
│       └── theme.js              # Alpine theme store
│
├── templates/
│   ├── cotton/                   # Django Cotton components (Atomic Design)
│   │   ├── atoms/                # Basic elements
│   │   │   ├── button.html
│   │   │   ├── input.html
│   │   │   ├── search_input.html
│   │   │   ├── link.html
│   │   │   ├── select.html
│   │   │   └── icon.html
│   │   │
│   │   ├── molecules/            # Combinations of atoms
│   │   │   ├── logo.html
│   │   │   ├── search_bar.html
│   │   │   └── topic_card.html
│   │   │
│   │   └── organisms/            # Complex sections
│   │       ├── header.html
│   │       ├── footer.html
│   │       ├── hero.html
│   │       └── topic_grid.html
│   │
│   ├── pages/
│   │   ├── home.html             # Landing page
│   │   ├── components.html       # Component library page
│   │   └── style_guide.html      # Style guide page
│   │
│   └── base.html                 # Base template (responsive layout)
│
├── portal/
│   ├── views.py                  # Page views
│   └── urls.py                   # URL routes
│
└── config/
    └── settings.py
```

---

## Design System Source

Our Tailwind config and CSS patterns are adapted from [CourtListener](https://github.com/freelawproject/courtlistener), using their:

- Color palette (greyscale, primary coral/red, brand purple)
- Typography (Inter, Cooper Hewitt fonts)
- Spacing scale
- Component patterns (buttons, inputs, alerts, etc.)

---

## Development Workflow

```bash
# Start dev server (Docker)
cp .env.example .env      # Add your GROQ_API_KEY
make docker-dev

# Production CSS build (minified)
tailwindcss -i src/css/main.css -o static/css/main.built.css --minify
```

**Requirements:** Python 3.13+, Tailwind CSS (`brew install tailwindcss`)

**Note:** We use Tailwind v4 with CSS-based configuration. Theme tokens are defined
in `@theme { }` blocks within `static/css/main.css` - no `tailwind.config.js` needed.

Visit http://portal.localhost:8000/style-guide/ to view component library.

---

## Future Considerations

If browser-based testing proves insufficient, consider:

1. **Playwright** - Automated viewport screenshots (Python, no Node needed)
2. **Storybook** - More comprehensive but requires Node.js
3. **Percy/Chromatic** - Visual regression testing

For now, browser DevTools + manual testing provides sufficient coverage for MVP.
