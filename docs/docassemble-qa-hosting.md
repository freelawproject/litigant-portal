# docassemble on QA over HTTPS

How docassemble is hosted at `https://qa.litigantportal.com/interview/` so the
Topic Flow link-out is clean for court-partner demos. Infra side of #531
(branding is #549).

> **Path, not subdomain — on purpose.** docassemble routes _under_ the existing
> LP hostname at `/interview/`, so a court partner needs only their one existing
> CNAME for the whole portal — no per-service DNS, portable between partners,
> self-hostable. Low-friction-for-partners is a guiding principle
> (ARCHITECTURE.md → Open Contracts).
>
> This is **QA hosting**, not the local authoring bench. The bench
> (`docker-compose.docassemble.yml`, `localhost:8100`) is unchanged — keep using
> it to author/test interviews. See `docassemble/nd-name-change/README.md`.

## How it works

docassemble is a service in the DO QA stack (`deploy/qa-do/docker-compose.qa.yml`)
— it deploys, restarts, and is removed with the rest of the box. (An earlier
standalone override, `docker-compose.docassemble.qa.yml`, was retired with the
CL-infra move; `deploy/qa-do/` is the single home now.)

Caddy reaches it as `docassemble:80` on the project network — no public port.
docassemble is mounted at the `/interview/` prefix via `POSTURLROOT` (it
regenerates its internal nginx for the sub-path); the `handle /interview/*`
block in `deploy/qa-do/Caddyfile.qa` passes the prefix through. Caddy terminates
TLS and forwards plain HTTP; docassemble runs with `BEHINDHTTPSLOADBALANCER=true`
so it still builds `https://` URLs and secure cookies.

**No new certificate.** Because `/interview/` is on the _existing_ LP hostname,
Caddy already serves TLS for it — there's no extra ACME/DNS challenge.

## Persistence (survives deploys)

docassemble keeps **all** state internally — its own Postgres, playground
files, server config, user accounts. The container is stateless only if you let
it be: its `initialize.sh` writes a full backup to
`/usr/share/docassemble/backup` on clean stop and nightly by cron, and restores
from it on boot.

The QA service therefore mounts two named volumes (see the compose comment):

- `docassemble_qa_backup:/usr/share/docassemble/backup` — the backup/restore
  cycle above; this is what makes recreates safe
- `docassemble_qa_files:/usr/share/docassemble/files` — live file storage

Supporting pieces:

- `stop_grace_period: 600s` — the shutdown backup needs time; a SIGKILL loses
  the delta **and** flags the next boot as an unsafe shutdown, which skips the
  restore.
- The compose `name: litigant-portal` pin resolves the volumes to
  `litigant-portal_docassemble_qa_*` on the box.

**History (#701):** the service ran without these volumes after the `deploy/qa-do/`
rebuild (#650), so a July 2026 deploy recreated it empty — interviews 404'd and
the admin login reset to its public default. If a recreate ever comes up empty
again, check `docker volume ls | grep docassemble` before re-uploading anything:
if the volumes exist, a recreate with the mounts restores them; only if they're
gone do you re-seed from `docassemble/nd-name-change/` (steps in that README).

## Prerequisites

- **QA at ≥ 4 GB RAM.** docassemble idles ~2 GB; co-tenant with the LP stack needs
  the 4 GB tier (#534). At 2 GB it OOMs.
- **No new DNS.** Uses the existing host record (`qa.litigantportal.com` already
  resolves to the droplet).
- **`DA_HOSTNAME`** in the box `.env` = the existing LP host as a **bare hostname**,
  e.g. `DA_HOSTNAME=qa.litigantportal.com`. docassemble needs its own hostname for
  URL building. ⚠️ Unlike `DOMAIN` (which is `https://qa.litigantportal.com`),
  `DA_HOSTNAME` has **no scheme** — a `https://` prefix makes docassemble build
  `https://https://…` URLs and breaks secure cookies.

## Deploy

Nothing docassemble-specific: it rides the manual QA deploy
(GitHub → Actions → **Deploy to DigitalOcean QA (manual)**), which syncs the box
tree and runs the whole stack via `deploy/qa-do/docker-compose.qa.yml`. First
boot pulls the ~20 GB image and inits docassemble's DB — give it **5–10 min**.

Verify:

```bash
curl -sI https://qa.litigantportal.com/interview/ | head -1   # 200 / 302 into docassemble
curl -sI https://qa.litigantportal.com/ | head -1             # LP root still 200
docker stats --no-stream                                      # docassemble ~2 GB, LP healthy
```

## After it's up

- **Load the interview** — restored automatically from the backup volume; on a
  truly fresh instance, upload the interviews + PDFs to the Playground (steps in
  `docassemble/nd-name-change/README.md`), or publish them as a package for a
  clean anonymous URL (#556).
- **Rotate the admin password** — a fresh instance boots with docassemble's
  public default login; change it before anything else. A restored instance
  keeps the rotated one.
- **Branding** — apply the LP look + download-only + anonymous config (#549).
- **Set the corpus `interview_url`** to `https://qa.litigantportal.com/interview/...`
  so the Topic Flow "Fill out your forms" button goes live (#543 seam).

## Troubleshooting

- **The interview loads but live updates hang** → the WebSocket isn't threading
  the `/interview/` prefix. Confirm `POSTURLROOT=/interview/` took (check
  docassemble's logs/nginx) and that Caddy's `reverse_proxy docassemble:80` is
  upgrading the socket. **Test this first.**
- **Assets/links 404 under `/interview/`** → `POSTURLROOT` not applied; recreate
  the container so `initialize.sh` regenerates nginx with the prefix.
- **Bare `/interview` (no trailing slash)** → redirected to `/interview/` with a
  308 (in `Caddyfile.qa`), so hand-typed/trailing-slash-stripped URLs still land.
- **Playground empty / default login after a recreate** → the state volumes
  weren't mounted (or an unsafe shutdown skipped the restore). See Persistence
  above before re-uploading by hand.
- **docassemble fails to initialize / builds wrong URLs** → `DA_HOSTNAME` unset
  (or scheme-prefixed) in the box `.env`. Compose substitutes an empty string
  with a warning — Caddy still starts (it uses `DOMAIN`, not `DA_HOSTNAME`),
  but docassemble runs with no hostname. Set a bare host in `.env`.

## At the AWS cutover

The DO _hosting path_ goes away with `deploy/qa-do/` (see its README), but
**docassemble itself persists** — it gets its own docker instance on the AWS
infra (#461). The state requirement travels with it: whatever runs it there
must mount `/usr/share/docassemble/backup` (volume or S3-backed), or the wipe
this doc's Persistence section describes happens again on the first recreate.
