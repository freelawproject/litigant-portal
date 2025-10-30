# Quick Start Guide

Get up and running with the Litigant Portal development environment in minutes.

## Prerequisites

- **Python 3.13+** with `uv` installed
- **Node.js 20+** - We recommend using [fnm](https://github.com/Schniz/fnm) for Node.js version management

### Installing fnm (if needed)

```bash
# macOS/Linux
curl -fsSL https://fnm.vercel.app/install | bash

# Then install Node.js (version specified in .node-version)
fnm install

# fnm will automatically use the correct version when you cd into the project
```

**Note**: The project includes a `.node-version` file, so fnm will automatically switch to the correct Node.js version when you enter the project directory (if you have fnm's shell integration enabled).

## Setup (First Time)

```bash
# 1. Clone and navigate to the project
cd litigant-portal

# 2. Create and activate virtual environment
uv venv
source .venv/bin/activate

# 3. Install all dependencies
make install

# 4. Run database migrations
make migrate

# 5. Start development servers
make dev
```

Visit **http://localhost:8000** to see the app!

## Daily Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Start both Django and Vite dev servers
make dev
```

## Common Commands

```bash
# Run tests
make test

# Lint and format code
make lint
make format

# Type checking
mypy portal config        # Python
npm run type-check        # TypeScript

# Build for production
make build
```

## Project Commands Reference

Run `make help` to see all available commands:

```bash
make help
```

## Next Steps

- Read the [Development Guide](./DEVELOPMENT.md) for detailed information
- Review [CourtListener Frontend Architecture](./CourtListener-Frontend-Architecture.md) for patterns
- Check [Vision](../VISION.md) and [Tech Stack](../TECH_STACK.md) documents

## Troubleshooting

### "Command not found: uv"

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Port already in use"

Kill existing processes:
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Find and kill process on port 5173
lsof -ti:5173 | xargs kill -9
```

### Vite assets not loading

Ensure both servers are running:
- Vite dev server: http://localhost:5173
- Django server: http://localhost:8000

Django fetches assets from Vite in development mode.

## Tech Stack Summary

- **Backend**: Django 5.2+ with django-cotton components
- **Frontend**: AlpineJS (TypeScript) + Tailwind CSS
- **Build**: Vite 6.x with Hot Module Replacement
- **Testing**: pytest (Python), Vitest (TypeScript)
- **Quality**: Ruff + mypy (Python), ESLint + Prettier (TypeScript)
