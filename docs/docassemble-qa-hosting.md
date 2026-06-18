# docassemble on QA over HTTPS

How to host the docassemble interview at `https://<lp-host>/interview/` (e.g.
`https://qa.litigantportal.com/interview/`) so the Topic Flow link-out is clean
for court-partner demos. Infra side of #531 (branding is #549).

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

A QA-only compose override (`docker-compose.docassemble.qa.yml`) layers on the
base compose. It adds a `docassemble` service to the LP project network so
**caddy-prod reaches it as `docassemble:80`** — no public port (unlike the bench's
`:8100`). docassemble is mounted at the `/interview/` prefix via `POSTURLROOT`
(it regenerates its internal nginx for the sub-path); Caddy passes the prefix
through. Caddy terminates TLS and forwards plain HTTP; docassemble runs with
`BEHINDHTTPSLOADBALANCER=true` so it still builds `https://` URLs and secure
cookies.

The route lives in `docker/caddy/conf.d/docassemble.caddy` as a `handle
/interview/*` block, pulled into the main `{$DOMAIN}` site by `import
conf.d/*.caddy`. The override mounts `conf.d` into caddy **only on QA**, so a
base-only (prod) deploy loads none of it — the glob matches nothing.

**No new certificate.** Because `/interview/` is on the _existing_ LP hostname,
Caddy already serves TLS for it — there's no extra ACME/DNS challenge.

## Prerequisites

- **QA at ≥ 4 GB RAM.** docassemble idles ~2 GB; co-tenant with the LP stack needs
  the 4 GB tier (#534). At 2 GB it OOMs.
- **No new DNS.** Uses the existing host record (`qa.litigantportal.com` already
  resolves to the droplet).
- **`DA_HOSTNAME`** in the QA `.env` = the existing LP host as a **bare hostname**,
  e.g. `DA_HOSTNAME=qa.litigantportal.com`. docassemble needs its own hostname for
  URL building. ⚠️ Unlike `DOMAIN` (which is `https://qa.litigantportal.com`),
  `DA_HOSTNAME` has **no scheme** — a `https://` prefix makes docassemble build
  `https://https://…` URLs and breaks secure cookies.

## Deploy

On `lp-qa`, from `/opt/litigant-portal`:

```bash
# Stop the local-bench container first if it's still running (frees :8100, avoids
# two docassemble instances):
docker rm -f docassemble-dev 2>/dev/null || true

# Bring up LP + docassemble together, behind Caddy:
docker compose -f docker-compose.yml -f docker-compose.docassemble.qa.yml \
  --profile prod up -d
```

First boot pulls the image and inits docassemble's own DB — give it **5–10 min**.
Then verify:

```bash
docker compose -f docker-compose.yml -f docker-compose.docassemble.qa.yml \
  --profile prod ps                                       # docassemble + LP all up
curl -sI https://qa.litigantportal.com/interview/ | head -1   # 200 / 302 into docassemble
curl -sI https://qa.litigantportal.com/ | head -1             # LP root still 200
docker stats --no-stream                                  # docassemble ~2 GB, LP healthy
```

## After it's up

- **Load the interview** — upload the interviews + `petition.pdf` to this
  instance's Playground (same steps as the bench README), or publish them as a
  package for a clean anonymous URL.
- **Branding** — apply the LP look + download-only + anonymous config (#549).
- **Set the corpus `interview_url`** to `https://qa.litigantportal.com/interview/...`
  so the Topic Flow "Fill out your forms" button goes live (#543 seam).

## Reboot durability

The service is `restart: unless-stopped`, so a reboot brings it back (pairs with
#548 for the LP stack). A cold boot starts LP + docassemble together on 2 vCPUs,
so there's a brief window where docassemble's init competes for CPU — LP recovers
once it settles.

## Troubleshooting

- **The interview loads but live updates hang** → the WebSocket isn't threading
  the `/interview/` prefix. This is the main thing to verify in path mode: confirm
  `POSTURLROOT=/interview/` took (check docassemble's logs/nginx) and that Caddy's
  `reverse_proxy docassemble:80` is upgrading the socket. **Test this first.**
- **Assets/links 404 under `/interview/`** → `POSTURLROOT` not applied; recreate
  the container so `initialize.sh` regenerates nginx with the prefix.
- **Bare `/interview` (no trailing slash)** → redirected to `/interview/` with a
  308 (in `conf.d/docassemble.caddy`), so hand-typed/trailing-slash-stripped URLs
  still land.
- **docassemble fails to initialize / builds wrong URLs** → `DA_HOSTNAME` unset (or
  scheme-prefixed) while the override is active. Compose substitutes an empty
  string with a warning — Caddy still starts (it uses `DOMAIN`, not `DA_HOSTNAME`),
  but docassemble runs with no hostname. Set a bare host in `.env`.

## Prod safety

Production deploys (`docker compose -f docker-compose.yml --profile prod up -d`,
no override) load **none** of this — no docassemble service, no `conf.d` mount, no
`/interview/` route. docassemble's real production home rides the CL infra move
(#461); this is the interim QA demo host.
