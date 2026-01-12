# Litigant Portal

Access to justice portal for self-represented litigants. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env      # Add your GROQ_API_KEY
make docker-dev           # Start dev environment
```

Visit: http://localhost:8000

### Docker Production

```bash
# Create secrets (see secrets/README.md)
mkdir -p secrets
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" > secrets/django_secret_key.txt
echo "your-db-password" > secrets/db_password.txt

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
- **Database:** PostgreSQL (Docker) / SQLite (local dev)

## License

AGPL-3.0. See [LICENSE](LICENSE).
