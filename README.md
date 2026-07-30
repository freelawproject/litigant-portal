# Litigant Portal

An access to justice portal that helps people navigate a legal case without an attorney. Self-represented litigants get plain-language, jurisdiction-specific guidance: an AI-guided chat, step-by-step Topic Flows for common case types, and document assembly for court forms. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env            # Add your OPENAI_API_KEY
make docker                     # Start dev environment
```

Visit: http://localhost (Caddy serves on port 80).

## Documentation

| Doc                                                   | Description                                           |
| ----------------------------------------------------- | ----------------------------------------------------- |
| [Docs index](docs/README.md)                          | The reference shelf: AI tooling, wiki, docassemble    |
| [Agent dev guide](docs/ai-tooling/AGENT_DEV_GUIDE.md) | Building agents on the chat engine                    |
| [docassemble](docs/docassemble.md)                    | Document assembly: authoring, local bench, QA hosting |
| [Security](docs/wiki/SECURITY.md)                     | Security architecture: CSP, headers, secrets          |

## Tech Stack

- **Backend:** Django 6.0
- **Components:** Django Cotton (server-rendered)
- **Styling:** Tailwind CSS v4 (standalone CLI)
- **Reactivity:** Alpine.js (CSP build)
- **AI:** LiteLLM (provider-agnostic chat engine)
- **Document assembly:** docassemble (path-routed add-on service)
- **Database:** PostgreSQL (pgvector)
- **Caching:** Redis

## Production

**Image:** built from `docker/django/Dockerfile`. Run it with the `web-prod` command — it collects static files, applies migrations, and serves gunicorn on port **8000**.

**Deployment principles:** the deploying court is a client too — minimize what a partner must operate. A partner points **one CNAME** at the app (`portal.theircourt.gov`) and everything serves under it: LP at `/`, add-on services by path (e.g. docassemble at `/interview/`), never a new subdomain — each subdomain is another DNS ticket for a court's IT. New add-on services claim a path, not a hostname. The portal is fully self-hostable; nothing may depend on infrastructure only we can run. Partner-facing data surfaces are validated contracts, not tool bindings — a conformant Topic Flow corpus works identically whether hand-authored, exported from a CMS, or AI-generated.

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

## Contributing

Issue-first workflow, Conventional Commits, WCAG AA floor — see [CONTRIBUTING.md](CONTRIBUTING.md). A signed [CLA](https://cla-assistant.io/freelawproject/litigant-portal) is required before merge (one click, covers all FLP repos); see the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

AGPL-3.0. See [LICENSE](LICENSE).
