# Django-Cotton Conversion Status

**Last Updated:** 2025-11-25
**Project:** ~/work/litigant-portal
**Source Repo:** ~/projects/lp-svelte (SvelteKit + UnoCSS)
**Target Stack:** Django-Cotton + Tailwind + AlpineJS

---

## 🎯 Quick Start

```bash
cd ~/work/litigant-portal
./dev.sh                    # Start both servers
# Visit: http://localhost:8000/components/
```

**Other Commands:**
```bash
make help                   # Show all commands
npm run build              # Build production assets
source .venv/bin/activate  # Activate Python env
python manage.py shell     # Django shell
```

---

## ✅ Completed (Phases 1 & 2)

### Phase 1: Django Foundation
- ✅ Django 5.2.7 project created (Python 3.13)
- ✅ Project structure: `config/` + apps (`portal`, `litigant_portal`)
- ✅ Database migrated (SQLite for development)
- ✅ **django-cotton** - Component system configured
- ✅ **django-vite** - Frontend asset integration
- ✅ **django-allauth** - Authentication system
- ✅ **django-csp** - Content Security Policy configured

**URLs Configured:**
- `/` - Home (placeholder for future app)
- `/components/` - Component library
- `/style-guide/` - Design tokens documentation
- `/admin/` - Django admin
- `/accounts/` - Authentication (allauth)

### Phase 2: Frontend Build Pipeline
- ✅ **Vite 6.0.7** - Fast bundler with HMR
- ✅ **Tailwind CSS 3.4.17** - Utility-first styling
- ✅ **AlpineJS 3.14.3** - Lightweight reactivity (CSP-safe)
- ✅ **JavaScript ES6+** - For Alpine stores and utilities
- ✅ **@tailwindcss/forms** - Better form defaults

**Design Tokens Migrated:**
- Primary colors (Chicago Blue: #41b6e6)
- Secondary colors (Red: #ea1c2c)
- Accent colors (Yellow: #ffc72c)
- Font families (Antonio, Roboto, Roboto Serif)
- Title sizes (title-1 through title-8)
- Spacing system (4px base unit)
- Mobile-first breakpoints (sm: 640px, md: 768px, lg: 1024px, xl: 1280px)

**Security:**
- ✅ CSP configured for AlpineJS + Vite dev server
- ✅ No `unsafe-eval` or `unsafe-inline` needed
- ✅ blob: and data: URIs enabled (camera/file uploads)

**Templates Created:**
- `templates/base.html` - Main layout with Vite asset loading
- `templates/layouts/mobile_base.html` - Mobile-optimized layout
- `templates/pages/home.html` - Home placeholder
- `templates/pages/components.html` - Component library
- `templates/pages/style_guide.html` - Design tokens documentation

---

## 📂 Project Structure

```
~/work/litigant-portal/
├── config/                     # Django settings
│   ├── settings.py            # Main configuration
│   ├── urls.py                # URL routing
│   └── wsgi.py                # WSGI entry point
│
├── portal/                     # Main Django app
│   ├── views.py               # View functions
│   └── urls.py                # App URLs
│
├── litigant_portal/            # Future app code (placeholder)
│
├── templates/                  # Django templates
│   ├── base.html              # Base layout
│   ├── cotton/                # Django-Cotton components
│   │   └── button.html        # Button component
│   ├── layouts/
│   │   └── mobile_base.html   # Mobile layout
│   └── pages/
│       ├── home.html          # Home placeholder
│       ├── components.html    # Component library
│       └── style_guide.html   # Design tokens
│
├── frontend/                   # Frontend source (pre-build)
│   └── src/
│       ├── main.js            # AlpineJS entry point
│       ├── styles/
│       │   ├── main.css       # Entry point
│       │   ├── base/          # Reset, typography, layout
│       │   ├── components/    # Button styles, etc.
│       │   └── utilities/     # Overrides
│       └── scripts/
│           └── stores/        # Alpine stores (theme)
│
├── static/                     # Vite build output
│   ├── .vite/manifest.json
│   ├── css/
│   └── js/
│
├── docs/                       # Project documentation
│
├── dev.sh                      # Start both servers
├── Makefile                    # Development commands
├── manage.py                   # Django management
├── package.json                # npm dependencies
├── vite.config.ts              # Vite configuration
├── tailwind.config.js          # Tailwind + design tokens
└── postcss.config.js           # PostCSS config
```

---

## 🔧 Configuration Files

### Django Settings Highlights
**File:** `config/settings.py`

```python
# Key configurations:
INSTALLED_APPS = [
    'django_cotton',           # Component system
    'django_vite',             # Asset integration
    'allauth',                 # Authentication
]

# Cotton components in templates/cotton/
COTTON_DIR = "cotton"

# Vite integration
DJANGO_VITE_DEV_MODE = DEBUG
DJANGO_VITE_DEV_SERVER_PORT = 5173

# CSP Security
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "http://localhost:5173" if DEBUG else None)
# AlpineJS v3+ is CSP-safe (no unsafe-eval needed)

# Template discovery
TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']
TEMPLATES[0]['OPTIONS']['builtins'] = [
    'django_cotton.templatetags.cotton',
]
```

### Vite Configuration
**File:** `vite.config.ts`

```typescript
export default defineConfig({
  base: '/static/',
  build: {
    manifest: true,
    outDir: 'static',
    rollupOptions: {
      input: {
        main: 'frontend/src/main.js',  // CSS imported here
      },
    },
  },
  server: {
    host: 'localhost',
    port: 5173,
  },
});
```

### Tailwind Configuration
**File:** `tailwind.config.js`

- Design tokens from lp-svelte migrated
- Mobile-first approach
- @tailwindcss/forms plugin
- Custom color palette (primary, secondary, accent)
- Custom font families (Antonio, Roboto, Roboto Serif)

---

## 🚀 Development Workflow

### Starting Development
```bash
cd ~/work/litigant-portal
./dev.sh
```

This starts:
- **Vite** dev server on http://localhost:5173 (HMR enabled)
- **Django** server on http://localhost:8000

### Making Changes
1. **Frontend code** (`frontend/src/`) - Hot reloads automatically
2. **Templates** (`templates/`) - Refresh browser to see changes
3. **Python code** (`*.py`) - Django auto-reloads

### Building for Production
```bash
npm run build
python manage.py collectstatic
```

### Testing the Setup
Visit http://localhost:8000/components/ to verify:
- ✅ Tailwind colors display correctly
- ✅ Button variants render (primary, secondary, tertiary, ghost)
- ✅ Dark mode toggle works (AlpineJS theme store)
- ✅ Focus rings visible (WCAG compliance)
- ✅ No CSP violations in console

Visit http://localhost:8000/style-guide/ to verify:
- ✅ Color palette displays
- ✅ Typography scale shows
- ✅ Spacing tokens render

---

## 📝 Next Steps (Phase 3)

### ✅ Completed
1. **Button component** - `templates/cotton/button.html`
   - Variants: primary, secondary, tertiary, ghost
   - Supports: disabled, full_width, custom classes
   - CSS in `frontend/src/styles/components/buttons.css`

### Remaining Tasks
1. **Convert Input component**
   - Source: `~/projects/lp-svelte/src/stories/atoms/input/`
   - Target: `templates/cotton/input.html`

2. **Convert remaining atoms** (Link, Select, Icon)

3. **Convert molecules** (FormField, Card, Alert)

4. **Convert organisms** (Header, SingleQuestionForm)

### Component Pattern
For each component:
1. Read Svelte source in `~/projects/lp-svelte/src/stories/`
2. Create Cotton template in `templates/cotton/[component].html`
3. Add CSS classes in `frontend/src/styles/components/`
4. Add AlpineJS for reactivity (if needed)
5. Add example to `/components/` page

### Component Structure
```
templates/cotton/
├── button.html         # <c-button>
├── input.html          # <c-input>
├── link.html           # <c-link>
└── ...
```

---

## 📚 Reference Documentation

### Project Docs (~/work/litigant-portal/docs/)
- **ATOMIC_DESIGN_ARCHITECTURE.md** - Original architecture plan
- **requirements-summary.md** - MVP requirements and UX principles
- **CONVERSION_STATUS.md** - This document

### Source Material (~/projects/lp-svelte/)
- `src/stories/atoms/` - Atom components to convert
- `src/stories/molecules/` - Molecule components
- `src/stories/organisms/` - Organism components
- `src/styles/design-tokens.css` - Design system (already migrated)
- `uno.config.ts` - UnoCSS config (reference for Tailwind conversion)

### External Documentation
- [Django-Cotton Docs](https://django-cotton.com/)
- [Django Pattern Library](https://github.com/torchbox/django-pattern-library)
- [AlpineJS v3 Docs](https://alpinejs.dev/)
- [Tailwind CSS Docs](https://tailwindcss.com/)
- [WCAG 2.1 AA Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

---

## 🔍 Troubleshooting

### Assets Not Loading (404 Errors)
```bash
# Clean build artifacts
rm -rf static/.vite static/css static/js

# Rebuild
npm run build

# Restart servers
./dev.sh
```

### CSP Violations
- Check browser console for specific violations
- Vite dev server must be whitelisted in `CSP_SCRIPT_SRC` during DEBUG
- AlpineJS v3+ doesn't need `unsafe-eval`

### Hot Reload Not Working
- Ensure Vite dev server is running (cyan output in terminal)
- Check that django-vite is detecting dev mode: `settings.DEBUG = True`
- Verify port 5173 is not blocked

### Pattern Library Not Showing Components
- Components must be in `PATTERN_LIBRARY.TEMPLATE_DIR` paths
- YAML fixture files must match template filenames
- Check `/pattern-library/` in DEBUG mode

---

## 🎯 Success Metrics

**Completed:**
- ✅ Django server running
- ✅ Vite dev server with HMR
- ✅ Tailwind compiling correctly
- ✅ AlpineJS reactive (theme store working)
- ✅ CSP compliant
- ✅ Mobile-first responsive
- ✅ Button component converted

**Next Milestones:**
- [x] Button atom converted
- [ ] Input atom converted
- [ ] 3 more atoms (Link, Select, Icon)
- [ ] 5 molecules (FormField, Card, Alert, Badge, ProgressIndicator)
- [ ] 1 organism (Header or SingleQuestionForm)
- [ ] WCAG AA compliance tested

---

## 📊 Tech Stack Summary

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Backend** | Django | 5.2.7 | Web framework |
| | Python | 3.13 | Language |
| | django-cotton | - | Component system |
| | django-allauth | - | Authentication |
| | django-csp | - | Security headers |
| **Frontend** | Vite | 6.x | Build tool |
| | Tailwind CSS | 3.4.x | Styling |
| | AlpineJS | 3.14.x | Reactivity |

---

## 🔗 Quick Links

- **Home:** http://localhost:8000/
- **Component Library:** http://localhost:8000/components/
- **Style Guide:** http://localhost:8000/style-guide/
- **Django Admin:** http://localhost:8000/admin/
- **Vite Dev Server:** http://localhost:5173/ (assets only)

---

**Status:** ✅ **Foundation Complete - Button Component Done**
**Next Session:** Convert Input component from `~/projects/lp-svelte/src/stories/atoms/input/`

---

## ⚠️ Workflow Guidelines

**For Future Sessions:**
- ✅ Provide **concise summaries** (not lengthy explanations)
- ⚠️ **Do NOT auto-execute changes** - propose and wait for approval
- ✅ Ask before creating new files or making changes
- ✅ Focus on one task at a time

**Latest Review:** See `docs/REVIEW_SUMMARY.md` for code review and cleanup recommendations
