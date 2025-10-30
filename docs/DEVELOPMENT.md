# Development Guide

## Tech Stack

This project uses a modern, CSP-compliant frontend stack:

- **Backend**: Django 5.2+
- **Components**: django-cotton (reusable HTML components)
- **Interactivity**: AlpineJS 3.x with TypeScript
- **Styling**: Tailwind CSS 3.x
- **Build Tool**: Vite 6.x
- **Testing**: pytest + pytest-django (Python), Vitest (TypeScript)
- **Linting/Formatting**: Ruff (Python), ESLint + Prettier (TypeScript)

## Prerequisites

- **Python 3.13+**
- **uv** (Python package manager)
- **Node.js 20+** with npm
- **fnm** (Fast Node Manager) - Recommended for Node.js version management

### Installing Prerequisites

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install fnm (Fast Node Manager)
curl -fsSL https://fnm.vercel.app/install | bash

# Install Node.js (uses .node-version file)
fnm install

# Verify installations
uv --version
node --version  # Should show v20.x.x
npm --version
```

**Note**: This project includes a `.node-version` file. When you have fnm's shell integration enabled, it will automatically switch to the correct Node.js version when you `cd` into the project directory.

## Initial Setup

All setup commands are **idempotent** and safe to re-run. If you've already completed setup, you can skip directly to [Running the Development Servers](#running-the-development-servers).

```bash
# Create virtual environment (safe to re-run if .venv already exists)
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies (safe to re-run - will skip if already installed)
make install

# Run migrations (safe to re-run - will only apply new migrations)
make migrate

# Build frontend assets (safe to re-run - will rebuild quickly)
npm run build
```

**Note**: All these commands are designed to be idempotent:
- `uv venv` will show a warning if `.venv` exists but won't break anything
- `make install` (uses `uv sync --extra dev`) quickly checks and only installs missing packages
- `make migrate` only applies unapplied migrations
- `npm run build` rebuilds efficiently with Vite's caching

## Development Workflow

### Running the Development Servers

The easiest way is to run both servers together:

```bash
make dev
```

This starts:
- **Vite dev server** at http://localhost:5173 (Hot Module Replacement)
- **Django server** at http://localhost:8000

Or run them separately:

```bash
# Terminal 1: Vite dev server
npm run dev

# Terminal 2: Django server
make run
```

### Code Quality

#### Linting

```bash
# Lint everything
make lint

# Lint Python only
ruff check .

# Lint TypeScript only
npm run lint
```

#### Formatting

```bash
# Format everything
make format

# Check formatting without changes
make format-check

# Format Python only
ruff format .

# Format TypeScript only
npm run format
```

#### Type Checking

```bash
# Python type checking
mypy portal config

# TypeScript type checking
npm run type-check
```

### Testing

```bash
# Run all tests
make test

# Python tests only
make test-py
# or: pytest

# JavaScript tests only
make test-js
# or: npm test

# JavaScript tests with UI
make test-js-ui
```

## Project Structure

```
litigant-portal/
├── config/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── portal/                 # Main Django app
│   ├── views.py
│   ├── models.py
│   └── ...
├── templates/              # Django templates
│   ├── base.html          # Base template
│   └── cotton/            # Cotton components
│       └── dropdown.html  # Example component
├── frontend/               # Frontend source code
│   └── src/
│       ├── css/
│       │   └── input.css  # Tailwind entry point
│       └── ts/
│           ├── main.ts    # TypeScript entry point
│           ├── types/     # TypeScript type definitions
│           └── alpine/
│               ├── components/  # Alpine components
│               ├── composables/ # Reusable utilities
│               └── plugins/     # Alpine plugins
├── static/                 # Static assets (source)
├── staticfiles/            # Built assets (generated)
├── tests/                  # Python tests
├── pyproject.toml         # Python config
├── package.json           # Node.js dependencies
├── vite.config.ts         # Vite configuration
├── tsconfig.json          # TypeScript configuration
└── tailwind.config.js     # Tailwind configuration
```

## Architecture Patterns

### Django Cotton Components

Components live in `templates/cotton/` with snake_case filenames.

**Creating a component** (`templates/cotton/my_component.html`):

```html
<c-vars title required description />

<div class="card">
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    {{ slot }}
</div>
```

**Using the component**:

```html
<c-my-component title="Hello" description="World">
    <p>This goes in the slot</p>
</c-my-component>
```

### AlpineJS + TypeScript (CSP-Compliant)

**CRITICAL**: No inline JavaScript allowed due to Content Security Policy.

All Alpine components must be registered in separate TypeScript files.

**Creating an Alpine component** (`frontend/src/ts/alpine/components/counter.ts`):

```typescript
import Alpine from 'alpinejs'
import type { AlpineComponent } from '../../types/alpine'

export interface CounterComponent extends AlpineComponent {
  count: number
  increment(): void
}

Alpine.data('counter', (): CounterComponent => ({
  count: 0,

  increment() {
    this.count++
  },
}))
```

**Register in main.ts**:

```typescript
import './alpine/components/counter'
```

**Using in templates**:

```html
<div x-data="counter">
    <button x-on:click="increment">Count: <span x-text="count"></span></button>
</div>
```

**Important conventions**:
- Always use `x-` prefix: `x-on:click`, not `@click`
- No inline expressions in templates
- Register all components via `Alpine.data()`

### Tailwind CSS

- Keep custom CSS minimal in `frontend/src/css/input.css`
- Use utility classes in templates
- Store brand colors in `tailwind.config.js`
- Classes must be complete strings (no dynamic concatenation)

❌ Bad: `class="text-{{ color }}"`
✅ Good: `class="{% if primary %}text-blue-600{% else %}text-gray-600{% endif %}"`

## Content Security Policy (CSP)

This project enforces a **strict Content Security Policy** to prevent XSS attacks.

**📖 See [CSP and Linting Guide](./CSP-AND-LINTING.md) for complete documentation.**

### Quick Overview

- ✅ CSP runs in **Report-Only mode** in development
- ✅ Violations appear in **browser DevTools Console**
- ❌ No inline JavaScript (`onclick="..."`) or inline styles allowed
- ✅ Alpine directives (`x-on:click`) are CSP-safe (they're attributes, not inline JS)

**To check for violations**:
1. Start dev server: `make dev`
2. Open browser DevTools → Console
3. Look for `[Report Only]` CSP violation messages
4. Fix violations by moving code to external files

### Debugging with Unminified Sources

In development mode, all JavaScript dependencies are served **unminified** with **source maps enabled**:

- **AlpineJS**: Uses unminified `module.esm.js` (3,407 lines) instead of minified version (5 lines)
- **Source Maps**: Generated for all built assets via `vite.config.ts`
- **CSP Relaxations**: Development mode allows `'unsafe-eval'` and `'unsafe-inline'` for debugging
- **Browser DevTools**: Can show original TypeScript source code with breakpoints

These debugging features are automatically disabled in production (`DEBUG = False`).

## Template Linting with djLint

**djLint** lints and formats Django templates for consistency and best practices.

```bash
# Lint templates
djlint templates/ --lint

# Format templates
djlint templates/ --reformat
```

Runs automatically via pre-commit hooks. See [CSP-AND-LINTING.md](./CSP-AND-LINTING.md) for details.

## Testing Patterns

### Python Tests (pytest)

```python
# tests/test_views.py
import pytest
from django.urls import reverse

def test_index_view(client):
    response = client.get(reverse('index'))
    assert response.status_code == 200
    assert 'Welcome' in response.content.decode()
```

### TypeScript Tests (Vitest)

```typescript
// frontend/src/ts/alpine/components/counter.test.ts
import { describe, it, expect } from 'vitest'

describe('Counter Component', () => {
  it('should increment', () => {
    const counter = createCounter()
    counter.increment()
    expect(counter.count).toBe(1)
  })
})
```

## Common Tasks

### Adding a New Page

1. Create template in `templates/`
2. Add view in `portal/views.py`
3. Add URL in `config/urls.py`

### Adding a New Cotton Component

1. Create `templates/cotton/component_name.html`
2. If needs interactivity, create TypeScript component
3. Use with `<c-component-name />`

### Adding Dependencies

```bash
# Python
uv pip install package-name

# Node.js
npm install package-name
```

## Production Build

```bash
# Build frontend assets
npm run build

# Collect static files
python manage.py collectstatic --noinput

# Or use make
make build
```

## Troubleshooting

### Vite assets not loading

- Ensure Vite dev server is running (`npm run dev`)
- Check `DJANGO_VITE` settings in `config/settings.py`
- Verify manifest.json exists in staticfiles after build

### Alpine component not working

- Check browser console for errors
- Verify component is imported in `main.ts`
- Ensure using `x-` prefix, not `@` or `:`
- Check for CSP violations in console

### TypeScript errors

```bash
# Check for type errors
npm run type-check

# Common fixes
npm install  # Install missing dependencies
```

### Test failures

```bash
# Run with verbose output
pytest -vv

# Run specific test
pytest tests/test_views.py::test_index_view

# JavaScript tests with UI
npm run test:ui
```

## Resources

- [Django Cotton Docs](https://django-cotton.com/)
- [AlpineJS Docs](https://alpinejs.dev/)
- [Tailwind CSS Docs](https://tailwindcss.com/)
- [Vite Docs](https://vite.dev/)
- [CourtListener Frontend Architecture](./CourtListener-Frontend-Architecture.md)
