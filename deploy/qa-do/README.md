# DigitalOcean QA deploy (temporary)

This directory and the `.github/workflows/qa-deploy-do.yml` workflow are a
**temporary** manual deploy path for the DigitalOcean QA box
(`qa.litigantportal.com`). It exists only until the AWS `qa-litigant`
environment is wired up (#587). Until then, DO QA is LP's only live environment.

## Why it exists

The manual DO deploy (`cd.yml`) was removed in #603, and the root
`docker-compose.yml` was reduced to local-dev only in #460 (prod moved to
CL/EKS infra). That left no way to deploy current `main` to the QA box. This
path restores that ability in isolation, without reintroducing prod services
into the local-dev compose.

## How to deploy

GitHub → Actions → **Deploy to DigitalOcean QA (manual)** → Run workflow →
pick the ref (default `main`). It builds the image, pushes `:qa` to Docker Hub,
and rolls it out on the box over SSH, then health-checks `/api/health/`.

## What it touches

- **Secrets:** `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `QA_HOST`, `QA_USER`,
  `QA_SSH_KEY` (all already in the repo).
- **Box `.env`** at `/opt/litigant-portal/.env` provides app config
  (`SECRET_KEY`, `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `DOMAIN`, `DA_HOSTNAME`,
  `ALLOWED_HOSTS`, `SITE_PASSWORD`, `CHAT_MODEL`).
- **Postgres:** a standalone containerized pgvector instance with its own
  docker-managed volume, seeded by the `web-prod` entrypoint's `migrate` on boot.
  It is **not** shared with AWS — the box's `POSTGRES_PASSWORD` is its own
  generated secret, independent of the EKS `litigant-env` secret. QA holds only
  seed/demo data; reset with `docker compose -f deploy/qa-do/docker-compose.qa.yml down -v`.

## Removal at AWS cutover

```bash
git rm -r deploy/qa-do .github/workflows/qa-deploy-do.yml
```

Nothing else references either — no edits to `docker-compose.yml`, `deploy.yml`,
or `staging-deploy.yml` to unwind.
