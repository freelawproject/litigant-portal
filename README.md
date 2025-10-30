# Litigant Portal

An open-source web application to democratize access to justice by empowering self-represented litigants with AI-augmented legal guidance, education, and document preparation tools.

Built by [Free Law Project](https://free.law) for use with CourtListener.com.

## Vision

To ensure that lack of financial resources never prevents anyone from understanding and exercising their legal rights.

See [VISION.md](./VISION.md) for our complete vision and mission statement.

## Tech Stack

Modern, type-safe web stack following best practices:

- **Backend**: Django 5.2+ with django-cotton components
- **Frontend**: AlpineJS (TypeScript) + Tailwind CSS
- **Build Tool**: Vite with Hot Module Replacement
- **Testing**: pytest (Python) + Vitest (TypeScript)
- **Code Quality**: Ruff + mypy (Python), ESLint + Prettier (TypeScript)

See [TECH_STACK.md](./TECH_STACK.md) for technical decisions and architecture.

## Quick Start

```bash
# Prerequisites: Python 3.13+, uv, fnm (for Node.js)

# Install Node.js (uses .node-version file)
fnm install

# Setup Python environment
uv venv && source .venv/bin/activate
make install
make migrate

# Start development
make dev
```

Visit http://localhost:8000

**📚 Detailed guides:**
- [Quick Start Guide](./docs/QUICKSTART.md)
- [Development Guide](./docs/DEVELOPMENT.md)
- [Setup Complete Reference](./docs/SETUP-COMPLETE.md)

## Development

```bash
# Run tests
make test              # All tests
make test-py          # Python only
make test-js          # TypeScript only

# Code quality
make lint             # Lint all code
make format           # Format all code
make type-check       # TypeScript type checking

# See all commands
make help
```

## Architecture

This project uses a **CSP-compliant architecture** following patterns from [CourtListener](https://github.com/freelawproject/courtlistener):

- **Django Cotton** - Reusable component system
- **AlpineJS** - Lightweight reactivity (no inline scripts)
- **TypeScript** - Type-safe frontend code
- **Tailwind CSS** - Utility-first styling
- **Vite** - Modern build pipeline

See [docs/CourtListener-Frontend-Architecture.md](./docs/CourtListener-Frontend-Architecture.md) for detailed patterns.

## Project Status

**Current Phase**: Initial development and prototype

- ✅ Tech stack configured
- ✅ Development environment set up
- ✅ Example components implemented
- 🚧 Core features in development

## Contributing

Contributions welcome! This project aims to improve access to justice globally.

1. Read the [Development Guide](./docs/DEVELOPMENT.md)
2. Check existing issues or create a new one
3. Fork and create a feature branch
4. Submit a pull request

## Documentation

- **[Quick Start](./docs/QUICKSTART.md)** - Get started in minutes
- **[Development Guide](./docs/DEVELOPMENT.md)** - Comprehensive development documentation
- **[CSP & Linting Guide](./docs/CSP-AND-LINTING.md)** - Content Security Policy and template linting
- **[Vision](./VISION.md)** - Project vision and principles
- **[Tech Stack](./TECH_STACK.md)** - Technical decisions and architecture
- **[Setup Complete](./docs/SETUP-COMPLETE.md)** - What's been configured
- **[Setup Review](./docs/SETUP-REVIEW.md)** - Issues found and fixed during setup

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE](./LICENSE) for full details.

Copyright 2025, Brian Carver and Michael Lissner.

Pull and feature requests welcome. Online editing in GitHub is possible (and easy!)
