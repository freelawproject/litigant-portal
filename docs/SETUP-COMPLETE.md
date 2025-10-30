# Setup Complete ✅

Your Litigant Portal development environment is fully configured!

## What's Been Set Up

### ✅ Django Backend
- Django 5.2.7 project structure
- `portal` app created
- django-cotton for reusable components
- django-vite for frontend integration
- WhiteNoise for static file serving
- CSP configuration for security

### ✅ Frontend Build Pipeline
- **Vite 6.x** - Modern, fast build tool with HMR
- **TypeScript 5.x** - Type-safe JavaScript
- **Tailwind CSS 3.x** - Utility-first CSS framework
- **AlpineJS 3.14** - Lightweight reactive framework
- **PostCSS** - CSS processing with autoprefixer

### ✅ Testing Frameworks
- **pytest + pytest-django** - Python testing
- **pytest-cov** - Code coverage
- **pytest-xdist** - Parallel test execution
- **Vitest** - Fast TypeScript/JavaScript testing
- **happy-dom** - Lightweight DOM for testing

### ✅ Code Quality Tools

#### Python
- **Ruff** - Lightning-fast linting AND formatting (replaces Black, isort, flake8)
- **mypy** - Static type checking
- **django-stubs** - Django type stubs for mypy

#### TypeScript
- **ESLint** - Linting with TypeScript support
- **Prettier** - Code formatting
- **TypeScript compiler** - Type checking

### ✅ Project Structure

```
litigant-portal/
├── config/                    # Django settings
├── portal/                    # Main app
├── templates/
│   ├── base.html             # Base template with Vite assets
│   ├── index.html            # Example page
│   └── cotton/
│       └── dropdown.html     # Example Cotton component
├── frontend/src/
│   ├── css/input.css         # Tailwind entry
│   └── ts/
│       ├── main.ts           # TypeScript entry
│       ├── types/            # Type definitions
│       └── alpine/
│           └── components/   # Alpine components
│               ├── dropdown.ts
│               └── dropdown.test.ts
├── docs/
│   ├── QUICKSTART.md         # Quick start guide
│   ├── DEVELOPMENT.md        # Detailed dev guide
│   └── CourtListener-Frontend-Architecture.md
├── Makefile                  # Convenient commands
├── pyproject.toml            # Python config
├── package.json              # Node.js config
├── vite.config.ts            # Vite config
├── vitest.config.ts          # Vitest config
├── tsconfig.json             # TypeScript config
├── tailwind.config.js        # Tailwind config
├── pytest.ini                # pytest config
└── .eslintrc.cjs             # ESLint config
```

## Node.js Version Management

This project includes a `.node-version` file set to Node.js 20. If you're using **fnm** (Fast Node Manager), it will automatically switch to the correct version when you enter the project directory.

```bash
# Install fnm if you haven't already
curl -fsSL https://fnm.vercel.app/install | bash

# Install the Node.js version specified in .node-version
fnm install

# fnm will auto-switch versions when you cd into the project
```

## Quick Commands

```bash
# Start development
make dev                 # Both Django + Vite servers

# Testing
make test               # All tests
make test-py           # Python only
make test-js           # TypeScript only

# Code quality
make lint              # Lint everything
make format            # Format everything
make type-check        # TypeScript types

# Database
make migrate           # Run migrations
make makemigrations    # Create migrations

# Build
make build             # Production build

# Help
make help              # See all commands
```

## Key Features

### 🔒 CSP-Compliant Architecture
- No inline JavaScript or CSS allowed
- All Alpine components in separate TypeScript files
- Strict Content Security Policy configured

### 🎨 Component-Based UI
- Django Cotton for reusable HTML components
- AlpineJS for interactivity
- Tailwind for styling

### 📦 Modern Build Pipeline
- Hot Module Replacement (HMR) in development
- Optimized production builds
- Source maps for debugging

### ✨ Type Safety
- Full TypeScript support for frontend
- mypy for Python type checking
- Type stubs for Django

### 🧪 Comprehensive Testing
- Unit tests for both Python and TypeScript
- Code coverage reports
- Fast test execution

## Example: Full Stack Feature

The project includes a working example showing all technologies together:

**Cotton Component** (`templates/cotton/dropdown.html`):
- Reusable dropdown UI component
- Styled with Tailwind CSS
- Uses Alpine for interactivity

**Alpine Component** (`frontend/src/ts/alpine/components/dropdown.ts`):
- TypeScript-based state management
- CSP-compliant registration
- Fully typed

**Tests** (`frontend/src/ts/alpine/components/dropdown.test.ts`):
- Vitest unit tests
- Type-safe test code

**Page** (`templates/index.html`):
- Uses the dropdown component
- Extends base template
- Loads Vite-compiled assets

## Next Steps

1. **Start Development**
   ```bash
   source .venv/bin/activate
   make dev
   ```
   Visit http://localhost:8000

2. **Read Documentation**
   - [Quick Start Guide](./QUICKSTART.md)
   - [Development Guide](./DEVELOPMENT.md)
   - [CourtListener Patterns](./CourtListener-Frontend-Architecture.md)

3. **Create Your First Component**
   - Add Cotton component in `templates/cotton/`
   - Add Alpine logic in `frontend/src/ts/alpine/components/`
   - Import in `main.ts`
   - Use in templates with `<c-your-component />`

4. **Write Tests**
   - Python: Add to `tests/`
   - TypeScript: Add `.test.ts` files next to components

## Architecture Decisions

### Why This Stack?

Based on CourtListener's proven architecture and your team's expertise:

1. **Django Cotton** - Familiar pattern, better than DTL includes
2. **AlpineJS** - Lightweight, no build complexity for simple interactions
3. **TypeScript** - Type safety without heavy framework overhead
4. **Tailwind** - Rapid UI development, consistent styling
5. **Vite** - Fast builds, excellent DX, modern tooling

### CSP Compliance

Content Security Policy prevents inline scripts/styles for security:
- ✅ Protects against XSS attacks
- ✅ Forces best practices
- ❌ Requires all Alpine in separate files
- ❌ Can't use `x-model` (needs unsafe-eval)

This matches production security requirements.

### Testing Strategy

**Unit Tests Now, Integration Later**
- Python: pytest for models, views, utils
- TypeScript: Vitest for Alpine components
- Future: Add integration tests with Playwright/Cypress

## Resources

- **Django**: https://docs.djangoproject.com/
- **django-cotton**: https://django-cotton.com/
- **AlpineJS**: https://alpinejs.dev/
- **Tailwind CSS**: https://tailwindcss.com/
- **Vite**: https://vite.dev/
- **Vitest**: https://vitest.dev/
- **Ruff**: https://docs.astral.sh/ruff/

## Troubleshooting

See [Development Guide](./DEVELOPMENT.md#troubleshooting) for common issues and solutions.

---

**Stack Summary**: Django + Cotton + AlpineJS (TypeScript) + Tailwind + Vite
**Testing**: pytest + Vitest
**Quality**: Ruff + mypy + ESLint + Prettier

Ready to build! 🚀
