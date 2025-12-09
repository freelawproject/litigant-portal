# Storybook Integration Plan

**Branch:** `django-atomic`

---

## Current Status

- [x] Planning complete
- [x] Docs consolidated
- [x] Task 1.1: django-pattern-library installed and configured
- [x] Task 1.2: Cotton compatibility verified (Button atom working)
- [x] Task 0.5: **Build simplification** - Removed Vite in favor of simpler stack
- [ ] **Next:** Create remaining atom patterns (Input, Link, Select, Icon)

**To resume:** Read `docs/README.md` for project context, then continue with Task 1.3 below.

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

| Decision                 | Choice                             | Rationale                                |
| ------------------------ | ---------------------------------- | ---------------------------------------- |
| **Folder structure**     | Keep `cotton/`, add YAML alongside | Minimal disruption, can reorganize later |
| **Storybook framework**  | HTML (not React)                   | No React in project, simpler setup       |
| **Pattern library tool** | django-pattern-library             | Required by storybook-django             |
| **A11y testing**         | @storybook/addon-a11y              | axe-core WCAG validation                 |
| **Viewport testing**     | @storybook/addon-viewport          | Device presets for mobile testing        |

---

## Implementation Tasks

### Phase 0: Build Simplification (Completed)

Simplified the frontend build stack before adding Storybook complexity.

**Rationale:** Vite was overkill for Alpine + Tailwind. Storybook will add Node.js
back for the component library, but production stack stays simpler.

| Before (Vite)                | After (Simplified)                    |
| ---------------------------- | ------------------------------------- |
| Vite dev server + HMR        | Tailwind CLI `--watch`                |
| `django_vite` template tags  | Django `{% static %}` tags            |
| Alpine via npm bundle        | Alpine via CDN (debug/prod variants)  |
| Vite manifest for hashing    | Django `ManifestStaticFilesStorage`   |
| `node_modules` always needed | Node.js only for Storybook (dev tool) |

**Changes made:**

- [x] Removed `vite.config.ts`
- [x] Removed `django_vite` from installed apps and settings
- [x] Updated `package.json` (removed vite, kept tailwind/prettier for now)
- [x] Converted `frontend/src/styles/` to `static/css/` for Tailwind CLI input
- [x] Moved theme store to `static/js/theme.js` (standalone, no bundling)
- [x] Updated templates to use Alpine CDN + `{% static %}` tags
- [x] Updated CSP settings for CDN domains
- [x] Simplified `dev.sh` to run Django + Tailwind CLI
- [x] Configured `ManifestStaticFilesStorage` for production

### Phase 1: Django Pattern Library Setup

- [x] **1.1** Configure pattern-library ✓
  - Added `django-pattern-library>=1.5.0` to dependencies
  - Configured `PATTERN_LIBRARY` settings in `config/settings.py`
  - Added URL routes for `/pattern-library/` (DEBUG only)
  - Created `templates/patterns/base.html` wrapper template

- [x] **1.2** Test Cotton compatibility ✓
  - Cotton components render correctly via wrapper templates
  - **Key learning:** Use separate pattern files per state (not YAML booleans)
  - Boolean attrs like `disabled: false` → string `"False"` (truthy) - use explicit templates instead

- [ ] **1.3** Create remaining atom patterns
  - [x] `templates/patterns/atoms/buttons/` (Primary, Secondary, Disabled)
  - [ ] `templates/patterns/atoms/inputs/`
  - [ ] `templates/patterns/atoms/links/`
  - [ ] `templates/patterns/atoms/selects/`
  - [ ] `templates/patterns/atoms/icons/`

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
  # Run Django + Tailwind + Storybook concurrently
  npx concurrently \
    --names "CSS,DJANGO,STORYBOOK" \
    "npx tailwindcss -i static/css/main.css -o static/css/main.built.css --watch" \
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

## File Structure (Current)

```
litigant-portal/
├── static/
│   ├── css/
│   │   ├── main.css              # Tailwind CLI input (source)
│   │   └── main.built.css        # Tailwind CLI output (generated)
│   └── js/
│       └── theme.js              # Alpine theme store
│
├── templates/
│   ├── cotton/                   # Cotton components (source)
│   │   ├── button.html
│   │   ├── input.html
│   │   ├── link.html
│   │   ├── select.html
│   │   └── icon.html
│   │
│   └── patterns/                 # Pattern library wrappers
│       ├── base.html             # Pattern wrapper (loads static assets)
│       └── atoms/
│           └── buttons/
│               ├── button.html + .yaml
│               ├── button_secondary.html + .yaml
│               └── button_disabled.html + .yaml
│
└── config/
    └── settings.py               # PATTERN_LIBRARY config
```

## File Structure (After Storybook)

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
│       └── ...
│
├── templates/patterns/      # (as above)
└── ...
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
        ('atoms', ['patterns/atoms']),  # Wrapper templates
    ),
    'TEMPLATE_SUFFIX': '.html',
    'PATTERN_BASE_TEMPLATE_NAME': 'patterns/base.html',
    'BASE_TEMPLATE_NAMES': ['base.html', 'patterns/base.html'],
}

# URL (in config/urls.py, DEBUG only):
# path('pattern-library/', include('pattern_library.urls'))
```

### Storybook Middleware (.storybook/middleware.js)

```javascript
const { createDjangoAPIMiddleware } = require('storybook-django/src/middleware')

module.exports = createDjangoAPIMiddleware({
  origin: 'http://localhost:8000',
  apiPath: ['/pattern-library/'],
})
```

### Example Story (stories/atoms/Button.stories.js)

```javascript
import { renderPattern } from 'storybook-django'

export default {
  title: 'Atoms/Button',
  parameters: {
    server: {
      url: '/pattern-library/render-pattern/cotton/button/',
    },
  },
}

export const Primary = {
  args: {
    variant: 'primary',
    slot: 'Primary Button',
  },
}

export const Secondary = {
  args: {
    variant: 'secondary',
    slot: 'Secondary Button',
  },
}

export const Disabled = {
  args: {
    variant: 'primary',
    slot: 'Disabled',
    disabled: true,
  },
}
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

| Service         | URL                                    | Purpose            |
| --------------- | -------------------------------------- | ------------------ |
| Django          | http://localhost:8000                  | Main app           |
| Storybook       | http://localhost:6006                  | Component library  |
| Pattern Library | http://localhost:8000/pattern-library/ | Django pattern API |

Note: Tailwind CLI runs in watch mode but doesn't serve assets - it just rebuilds CSS.

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

| Risk                          | Mitigation                                                     |
| ----------------------------- | -------------------------------------------------------------- |
| Cotton tag mocking complexity | Test early in Phase 1; fallback to wrapper templates if needed |
| storybook-django experimental | Actively maintained (July 2025); can fork if needed            |
| Two dev servers + CSS watcher | Use concurrently; simpler than before (no Vite)                |
| CSP conflicts with Storybook  | Add localhost:6006 to dev CSP whitelist                        |
| Alpine CDN availability       | jsDelivr is highly reliable; fallback to unpkg if needed       |

---

## References

- [storybook-django](https://github.com/torchbox/storybook-django) - Storybook integration
- [django-pattern-library](https://torchbox.github.io/django-pattern-library/) - Backend for pattern rendering
- [@storybook/addon-a11y](https://storybook.js.org/addons/@storybook/addon-a11y) - Accessibility testing
- [@storybook/addon-viewport](https://storybook.js.org/addons/@storybook/addon-viewport) - Device testing
- [Django Cotton](https://django-cotton.com/) - Component syntax

---

## Status

**Current:** Phase 1 in progress - django-pattern-library working with Cotton
**Completed:** Tasks 1.1, 1.2 (Button atom patterns)
**Next:** Task 1.3 - Create remaining atom patterns (Input, Link, Select, Icon)
