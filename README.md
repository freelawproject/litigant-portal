# Litigant Portal

Access to justice portal for self-represented litigants. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env      # Add your OPENAI_API_KEY
make docker-dev           # Start dev environment
```

Visit: http://localhost

### Docker Production

```bash
cp .env.example .env      # Set OPENAI_API_KEY, SECRET_KEY, ALLOWED_HOSTS, DOMAIN, POSTGRES_PASSWORD
make docker-prod
```

## Documentation

| Doc                                     | Description                      |
| --------------------------------------- | -------------------------------- |
| [Architecture](docs/ARCHITECTURE.md)    | Tech stack, patterns, Docker     |
| [Components](docs/COMPONENT_LIBRARY.md) | UI component library             |
| [Security](docs/SECURITY.md)            | CSP, secrets, production headers |

## Tech Stack

- **Backend:** Django 5.2 LTS
- **Components:** Django Cotton (server-rendered)
- **Styling:** Tailwind CSS (standalone CLI)
- **Reactivity:** Alpine.js (standard build)
- **Database:** PostgreSQL (pgvector)

## License

AGPL-3.0. See [LICENSE](LICENSE).
