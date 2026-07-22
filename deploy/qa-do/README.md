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
- **Static files:** bind-mounted from `/opt/litigant-portal/qa-static` on the
  box. Django (`web-prod` entrypoint) runs `collectstatic` into it; Caddy serves
  it read-only at `/static/`. A Docker named volume can't be used here — it inits
  root-owned and the container runs as non-root `appuser`, so `collectstatic`
  would fail. See one-time setup below.
- **docassemble state:** named volumes on `/usr/share/docassemble/backup` and
  `/files` — docassemble backs itself up there (clean stop + nightly) and
  restores on boot, so playground interviews, config, and the admin password
  survive deploys. Without them a recreate wipes everything and resets the admin
  login to its public default (#701, the 2026-07 wipe). If a recreate ever comes
  up empty anyway (unsafe shutdown skips the restore), re-seed from
  `docassemble/nd-name-change/` per that folder's README.

## One-time box setup (static directory)

The static bind-mount dir must exist and be owned by the container's `appuser`
uid before the first deploy:

```bash
# 1. Find appuser's uid in the image (expected: 1000)
docker run --rm --entrypoint id freelawproject/litigant-portal:qa -u

# 2. Create the dir and chown it to that uid (substitute if not 1000)
mkdir -p /opt/litigant-portal/qa-static
sudo chown -R 1000:1000 /opt/litigant-portal/qa-static
```

`collectstatic --clear` refreshes the _contents_ each deploy but leaves the
dir's ownership intact, so this chown is one-time. (The old root-owned
`litigant-portal_qa_static` named volume from earlier attempts can be removed:
`docker volume rm litigant-portal_qa_static`.)

## Removal at AWS cutover

```bash
git rm -r deploy/qa-do .github/workflows/qa-deploy-do.yml
```

Nothing else references either — no edits to `docker-compose.yml`, `deploy.yml`,
or `staging-deploy.yml` to unwind.
