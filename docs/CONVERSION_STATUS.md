# Django-Cotton Conversion Status

**Last Updated:** 2025-11-24
**Project:** ~/work/litigant-portal
**Source Repo:** ~/projects/lp-svelte (SvelteKit + UnoCSS)
**Target Stack:** Django-Cotton + Tailwind + AlpineJS

---

## 🎯 Quick Start

```bash
cd ~/work/litigant-portal
./dev.sh                    # Start both servers
# Visit: http://localhost:8000/demo/
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
- ✅ Django 4.2.25 project created (Python 3.13)
- ✅ Project structure: `config/` + apps (`portal`, `litigant_portal`)
- ✅ Database migrated (SQLite for development)
- ✅ **django-cotton** (2.1.3) - Component system configured
- ✅ **django-pattern-library** (1.5.0) - Component docs at `/pattern-library/`
- ✅ **django-vite** (3.1.0) - Frontend asset integration
- ✅ **djangorestframework** - REST API ready
- ✅ **django-allauth** - Authentication system
- ✅ **django-csp** (4.0) - Content Security Policy configured

**URLs Configured:**
- `/admin/` - Django admin
- `/accounts/` - Authentication (allauth)
- `/api/` - REST API endpoints
- `/pattern-library/` - Component library (DEBUG only)
- `/demo/` - Tech stack demo page

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
- `templates/templates/mobile_base.html` - Mobile-optimized layout
- `templates/pages/demo.html` - Tech stack test page

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
├── litigant_portal/            # Component app
│
├── templates/                  # Django templates (Atomic Design)
│   ├── base.html              # Base layout
│   ├── atoms/                 # Ready for components
│   ├── molecules/
│   ├── organisms/
│   ├── templates/
│   │   └── mobile_base.html
│   └── pages/
│       └── demo.html
│
├── frontend/                   # Frontend source (pre-build)
│   └── src/
│       ├── main.js            # AlpineJS entry point
│       ├── styles/
│       │   └── main.css       # Tailwind + design tokens
│       └── scripts/
│           ├── components/    # Alpine components
│           └── stores/        # Alpine stores
│
├── static/                     # Vite build output
│   ├── .vite/
│   │   └── manifest.json
│   ├── css/
│   └── js/
│
├── docs/                       # Project documentation
│   ├── ATOMIC_DESIGN_ARCHITECTURE.md
│   ├── requirements-summary.md
│   └── CONVERSION_STATUS.md   # This file
│
├── .venv/                      # Python virtual environment
├── node_modules/               # npm dependencies
│
├── dev.sh                      # Start both servers
├── Makefile                    # Development commands
├── manage.py                   # Django management
├── package.json                # npm dependencies
├── vite.config.ts              # Vite configuration
├── tailwind.config.js          # Tailwind + design tokens
├── postcss.config.js           # PostCSS config
├── pyproject.toml              # Python project metadata
└── .pre-commit-config.yaml     # Pre-commit hooks
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
    'pattern_library',         # Component docs
    'rest_framework',          # REST API
    'allauth',                 # Authentication
]

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
    'pattern_library.loader_tags',
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
Visit http://localhost:8000/demo/ to verify:
- ✅ Tailwind colors display correctly
- ✅ AlpineJS counter works (reactivity test)
- ✅ Focus rings visible (WCAG compliance)
- ✅ No CSP violations in console
- ✅ Mobile responsive grid

---

## 📝 Next Steps (Phase 3)

### Immediate Tasks
1. **Convert Button atom** from lp-svelte
   - Source: `~/projects/lp-svelte/src/stories/atoms/button/`
   - Target: `templates/atoms/button/button.html`
   - Add Pattern Library fixture: `templates/atoms/button/button.yaml`

2. **Convert Input atom**
   - Source: `~/projects/lp-svelte/src/stories/atoms/input/`
   - Target: `templates/atoms/input/input.html`

3. **Convert remaining atoms** (Link, Select, Icon)

4. **Convert molecules** (CategoryCard, SearchInput, etc.)

5. **Convert organisms** (Header)

### Component Conversion Pattern
For each component:
1. Read Svelte source in `~/projects/lp-svelte/src/stories/`
2. Create Cotton template in `templates/[atoms|molecules|organisms]/[component]/`
3. Convert styles to Tailwind utility classes
4. Add AlpineJS for reactivity (if needed)
5. Create Pattern Library fixture (YAML)
6. Document usage in markdown
7. Test in `/pattern-library/`

### Co-located Component Structure
Each component folder should contain:
```
templates/atoms/button/
├── button.html         # Cotton component template
├── button.yaml         # Pattern Library fixture
├── button.md           # Usage documentation
└── __init__.py         # Python module marker
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
- ✅ AlpineJS reactive
- ✅ CSP compliant
- ✅ Mobile-first responsive

**Next Milestones:**
- [ ] 5 atoms converted (Button, Input, Link, Select, Icon)
- [ ] 5 molecules converted (CategoryCard, SearchInput, etc.)
- [ ] 1 organism converted (Header)
- [ ] All components documented in Pattern Library
- [ ] WCAG AA compliance tested

---

## 📊 Tech Stack Summary

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Backend** | Django | 4.2.25 | Web framework |
| | Python | 3.13 | Language |
| | django-cotton | 2.1.3 | Component system |
| | django-pattern-library | 1.5.0 | Component docs |
| | djangorestframework | 3.16.1 | REST API |
| | django-allauth | 65.13.1 | Authentication |
| | django-csp | 4.0 | Security headers |
| **Frontend** | Vite | 6.0.7 | Build tool |
| | Tailwind CSS | 3.4.17 | Styling |
| | AlpineJS | 3.14.3 | Reactivity |
| **Dev Tools** | concurrently | 9.2.1 | Multi-process runner |
| | ruff | 0.14.6 | Python linting |
| | pre-commit | 4.5.0 | Git hooks |

---

## 🔗 Quick Links

- **Demo Page:** http://localhost:8000/demo/
- **Pattern Library:** http://localhost:8000/pattern-library/
- **Django Admin:** http://localhost:8000/admin/
- **Vite Dev Server:** http://localhost:5173/ (assets only)

---

**Status:** ✅ **Foundation Complete - Ready for Component Migration**
**Next Session:** Start with Button atom conversion from `~/projects/lp-svelte/src/stories/atoms/button/`

---

## ⚠️ Workflow Guidelines

**For Future Sessions:**
- ✅ Provide **concise summaries** (not lengthy explanations)
- ⚠️ **Do NOT auto-execute changes** - propose and wait for approval
- ✅ Ask before creating new files or making changes
- ✅ Focus on one task at a time

**Latest Review:** See `docs/REVIEW_SUMMARY.md` for code review and cleanup recommendations
