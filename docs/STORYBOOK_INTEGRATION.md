# Storybook Integration Plan

**Created:** 2025-12-08
**Status:** Planning
**Branch:** `django-atomic`

---

## Overview

Integrate [storybook-django](https://github.com/torchbox/storybook-django) with our existing Django Cotton component library to enable:

- **A11y testing** - WCAG 2.x compliance via axe-core
- **Viewport testing** - Mobile-first, older device support
- **Stakeholder demos** - Interactive component browsing
- **Developer documentation** - Living component library

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Storybook UI                       │
│  (Component browser, a11y panel, viewport switcher)     │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP API calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              django-pattern-library                     │
│  (Renders Django/Cotton templates with YAML context)    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 Django Cotton                           │
│  (templates/cotton/*.html + YAML context files)         │
└─────────────────────────────────────────────────────────┘
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Folder structure** | Keep `cotton/`, add YAML alongside | Minimal disruption, can reorganize later |
| **Storybook framework** | HTML (not React) | No React in project, simpler setup |
| **Pattern library tool** | django-pattern-library | Required by storybook-django |
| **A11y testing** | @storybook/addon-a11y | axe-core WCAG validation |
| **Viewport testing** | @storybook/addon-viewport | Device presets for mobile testing |

---

## Implementation Tasks

### Phase 1: Django Pattern Library Setup

- [ ] **1.1** Configure pattern-library to use `cotton/` folder
  - Add `django-pattern-library` to Python dependencies
  - Configure `PATTERN_LIBRARY` settings
  - Add URL routes for `/pattern-library/`
  - Create base pattern template

- [ ] **1.2** Test Cotton compatibility
  - Verify `<c-button>`, `<c-input>` etc. render
  - Mock Cotton template tags if needed
  - Test heroicons integration

- [ ] **1.3** Create YAML context files
  - `templates/cotton/button.yaml`
  - `templates/cotton/input.yaml`
  - `templates/cotton/link.yaml`
  - `templates/cotton/select.yaml`
  - `templates/cotton/icon.yaml`

### Phase 2: Storybook Setup

- [ ] **2.1** Install Storybook with HTML framework
  ```bash
  npx storybook@latest init --type html --no-dev
  npm install --save-dev storybook-django
  ```

- [ ] **2.2** Configure storybook-django middleware
  - Create `.storybook/middleware.js`
  - Proxy requests to Django pattern-library API
  - Configure webpack for HTML template loading

- [ ] **2.3** Write component stories
  - `stories/atoms/Button.stories.js`
  - `stories/atoms/Input.stories.js`
  - `stories/atoms/Link.stories.js`
  - `stories/atoms/Select.stories.js`
  - `stories/atoms/Icon.stories.js`

### Phase 3: Testing Addons

- [ ] **3.1** Add @storybook/addon-a11y
  ```bash
  npx storybook add @storybook/addon-a11y
  ```
  - Configure WCAG 2.1 AA rules
  - Add to all stories

- [ ] **3.2** Add @storybook/addon-viewport
  ```bash
  npx storybook add @storybook/addon-viewport
  ```
  - Configure mobile-first presets
  - Add older device sizes (Galaxy S5, iPhone SE)

### Phase 4: Development Integration

- [ ] **4.1** Update dev.sh
  ```bash
  # Run Django + Vite + Storybook concurrently
  npx concurrently \
    --names "VITE,DJANGO,STORYBOOK" \
    "npm run vite" \
    "python manage.py runserver" \
    "npm run storybook"
  ```

- [ ] **4.2** Update package.json scripts
  ```json
  {
    "scripts": {
      "storybook": "storybook dev -p 6006",
      "build-storybook": "storybook build"
    }
  }
  ```

- [ ] **4.3** Update CSP for Storybook dev server

### Phase 5: Stretch Goal

- [ ] **5.1** Reorganize to full atomic design
  ```
  templates/
    patterns/
      atoms/
        button.html
        button.yaml
      molecules/
      organisms/
  ```
  - Update `COTTON_DIR` setting
  - Update `PATTERN_LIBRARY['SECTIONS']`
  - Update all story imports

---

## File Structure (After Implementation)

```
litigant-portal/
├── .storybook/
│   ├── main.js              # Storybook config
│   ├── preview.js           # Story defaults
│   └── middleware.js        # Django API proxy
│
├── stories/
│   └── atoms/
│       ├── Button.stories.js
│       ├── Input.stories.js
│       ├── Link.stories.js
│       ├── Select.stories.js
│       └── Icon.stories.js
│
├── templates/
│   └── cotton/
│       ├── button.html      # Existing
│       ├── button.yaml      # NEW: context for pattern-library
│       ├── input.html       # Existing
│       ├── input.yaml       # NEW
│       ├── link.html        # Existing
│       ├── link.yaml        # NEW
│       ├── select.html      # Existing
│       ├── select.yaml      # NEW
│       ├── icon.html        # Existing
│       └── icon.yaml        # NEW
│
└── config/
    └── settings.py          # Add PATTERN_LIBRARY config
```

---

## Configuration Reference

### Django Settings (config/settings.py)

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'pattern_library',
]

PATTERN_LIBRARY = {
    'SECTIONS': (
        ('cotton', ['cotton']),  # Point to templates/cotton/
    ),
    'TEMPLATE_SUFFIX': '.html',
    'PATTERN_BASE_TEMPLATE_NAME': 'patterns/base.html',
    'BASE_TEMPLATE_NAMES': ['base.html'],
}
```

### Storybook Middleware (.storybook/middleware.js)

```javascript
const { createDjangoAPIMiddleware } = require('storybook-django/src/middleware');

module.exports = createDjangoAPIMiddleware({
  origin: 'http://localhost:8000',
  apiPath: ['/pattern-library/'],
});
```

### Example Story (stories/atoms/Button.stories.js)

```javascript
import { renderPattern } from 'storybook-django';

export default {
  title: 'Atoms/Button',
  parameters: {
    server: {
      url: '/pattern-library/render-pattern/cotton/button/',
    },
  },
};

export const Primary = {
  args: {
    variant: 'primary',
    slot: 'Primary Button',
  },
};

export const Secondary = {
  args: {
    variant: 'secondary',
    slot: 'Secondary Button',
  },
};

export const Disabled = {
  args: {
    variant: 'primary',
    slot: 'Disabled',
    disabled: true,
  },
};
```

### Example YAML Context (templates/cotton/button.yaml)

```yaml
context:
  variant: 'primary'
  slot: 'Click me'
  type: 'button'
  disabled: false
  full_width: false

# Tag overrides (if needed for Cotton)
tags: {}
```

---

## Development URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Django | http://localhost:8000 | Main app |
| Vite | http://localhost:5173 | Asset HMR |
| Storybook | http://localhost:6006 | Component library |
| Pattern Library | http://localhost:8000/pattern-library/ | Django pattern API |

---

## Testing Checklist

### A11y (WCAG 2.1 AA)

For each component in Storybook:
- [ ] No axe-core violations (check a11y panel)
- [ ] Color contrast 4.5:1 minimum
- [ ] Touch targets 44x44px minimum
- [ ] Keyboard navigable (Tab, Enter, Space)
- [ ] Focus indicators visible
- [ ] ARIA labels where needed

### Viewport Testing

Test each component at these sizes:
- [ ] iPhone SE (375x667) - small phone
- [ ] iPhone 12 (390x844) - standard phone
- [ ] Galaxy Fold (280x653) - narrow foldable
- [ ] iPad (768x1024) - tablet
- [ ] Desktop (1280x800) - laptop

---

## Dependencies to Add

### Python (pyproject.toml or requirements.txt)

```
django-pattern-library>=1.0.0
```

### Node (package.json)

```json
{
  "devDependencies": {
    "@storybook/addon-a11y": "^8.0.0",
    "@storybook/addon-viewport": "^8.0.0",
    "@storybook/html": "^8.0.0",
    "storybook": "^8.0.0",
    "storybook-django": "^0.5.0"
  }
}
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Cotton tag mocking complexity | Test early in Phase 1; fallback to wrapper templates if needed |
| storybook-django experimental | Actively maintained (July 2025); can fork if needed |
| Three dev servers (Django+Vite+Storybook) | Already using concurrently; add third process |
| CSP conflicts with Storybook | Add localhost:6006 to dev CSP whitelist |

---

## References

- [storybook-django](https://github.com/torchbox/storybook-django) - Storybook integration
- [django-pattern-library](https://torchbox.github.io/django-pattern-library/) - Backend for pattern rendering
- [@storybook/addon-a11y](https://storybook.js.org/addons/@storybook/addon-a11y) - Accessibility testing
- [@storybook/addon-viewport](https://storybook.js.org/addons/@storybook/addon-viewport) - Device testing
- [Django Cotton](https://django-cotton.com/) - Component syntax

---

## Status

**Current:** Planning complete, ready for implementation
**Next:** Task 1.1 - Install and configure django-pattern-library
