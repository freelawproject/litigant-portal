# Litigant Portal

Access to justice portal for self-represented litigants. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env            # Add your OPENAI_API_KEY
make docker                     # Start dev environment
```

Visit: http://localhost

## Production

**Image:** built from `docker/django/Dockerfile`. Run it with the `web-prod` command — it collects static files, applies migrations, and serves gunicorn on port **8000**.

**Runtime dependencies:**

- **PostgreSQL** with the **pgvector** extension.
- **Redis**

**Required environment** (see `.env.example`):

| Variable                                                                                  | Description                                   |
| ----------------------------------------------------------------------------------------- | --------------------------------------------- |
| `SECRET_KEY`                                                                              | Django secret key                             |
| `DEBUG=false`, `DEPLOYMENT_ENV`                                                           | Prod mode + environment label (`qa` / `prod`) |
| `ALLOWED_HOSTS`                                                                           | Comma-separated hostnames the app serves      |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Postgres connection                           |
| `REDIS_URL`                                                                               | Redis connection URL                          |
| `OPENAI_API_KEY` (or other provider key)                                                  | Chat provider credential                      |
| `CHAT_MODEL`                                                                              | LiteLLM model id                              |

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
- **Caching:** Redis

## License

AGPL-3.0. See [LICENSE](LICENSE).
