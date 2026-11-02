# Litigant Portal

An access to justice portal that helps people navigate a legal case without an attorney. Self-represented litigants get plain-language, jurisdiction-specific guidance: an AI-guided chat, step-by-step Topic Flows for common case types, and document assembly for court forms. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env            # Add your AWS_BEARER_TOKEN_BEDROCK
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

| Variable                                                                                  | Description                                     |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `SECRET_KEY`                                                                              | Django secret key                               |
| `DEBUG=false`, `DEPLOYMENT_ENV`                                                           | Prod mode + environment label (`qa` / `prod`)   |
| `ALLOWED_HOSTS`                                                                           | Comma-separated hostnames the app serves        |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Postgres connection                             |
| `REDIS_URL`                                                                               | Redis connection URL                            |
| `AWS_BEARER_TOKEN_BEDROCK`                                                                | AWS Bedrock API key                             |
| `AWS_REGION`                                                                              | Source region for model discovery and inference |

FLP curates model families in `litigant_portal/agents/bedrock.py`. `MODEL_MAPPING` names supported families, and the ordered Economy, Balanced, and Best lists in `MODEL_CHOICES` enable them. Dropdowns show available models with their resolved version and tier. An unset fast model uses the first available Economy choice; an unset assistant uses the first available Balanced choice, falling back only to Economy. Economy includes GPT Luna, Claude Haiku, and GLM Flash in that order. Judging stays disabled until selected. With the current curation, assistant/fast defaults are GPT Terra/GPT Luna, replacing the previous GPT Luna/Claude Haiku defaults. Saved selections are retained when unavailable or when discovery cannot confirm availability.

Each deployment uses its Bedrock key and `AWS_REGION` to discover the latest eligible release in the selected family. For that release, inference prefers a native regional route, then a compatible regional Mantle route, then an inference profile whose destinations all stay in the US. Global routing is excluded. `BEDROCK_ALLOWED_GEOGRAPHY` is optional: omitted or blank values default to `US`, and other values are rejected before discovery. `AWS_REGION` is optional: omitted or blank values default to `us-east-1`, and explicit region overrides are preserved. Local Compose uses the same region and geography defaults. A complete catalog, including native model access, is cached for one hour per credential and configuration fingerprint. Partial catalogs are cached for five minutes and sanitized discovery failures for one minute. Complete and partial catalogs refresh on request after 55 and four minutes respectively, while concurrent readers can reuse the unexpired snapshot. Refresh starts are shared across workers and limited to once per minute per fingerprint. Failed refreshes fail closed; expired catalogs are not reused. Family selections can adopt a newer eligible release after refresh, and accounts with different access can resolve differently. Authorization or missing-model errors request a refresh within that limit; ordinary bad-input errors do not. Failed inference is never replayed automatically. Attachments that the assistant cannot consume inline become reader stubs. The reader prefers the selected assistant when capable, otherwise the first enabled capable model in Economy, Balanced, then Best order without changing the saved selection. Titles, judging, and document reading use curated low-effort GPT options independently of pricing metadata; reader answers that reach the output limit are marked incomplete in the tool result and displayed response. The key needs permission to list foundation models and inference profiles, check foundation model availability, list Mantle models, and invoke the selected models.

## Contributing

Issue-first workflow, Conventional Commits, WCAG AA floor — see [CONTRIBUTING.md](CONTRIBUTING.md). A signed [CLA](https://cla-assistant.io/freelawproject/litigant-portal) is required before merge (one click, covers all FLP repos); see the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

AGPL-3.0. See [LICENSE](LICENSE).
