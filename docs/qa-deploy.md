# QA on EKS — how deploys work

QA is `qa.litigantportal.com`: the `qa-litigant` namespace on the `courtlistener` EKS cluster (us-west-2). It replaced the DigitalOcean box, which is a dev sandbox now (see [deploy/qa-do/README.md](../deploy/qa-do/README.md)) and is removed entirely at cutover. Prod is the sibling `litigant` namespace on the same cluster and deploys automatically from `main` (`.github/workflows/deploy.yml`); QA deploys are always manual.

This doc covers the app side — what a deploy does, what it deliberately does not touch, and how to verify. The cluster itself (manifests, secrets values, ingress, the docassemble workload) is infra-team territory and lives outside this repo; changes there are an infra ask, like #881 was.

## Deploying

GitHub → Actions → **Deploy to QA (EKS)** → Run workflow, or:

```bash
gh workflow run qa-deploy.yml -f deploy_ref=<branch> -f reset_db=true
```

Two inputs:

- **`deploy_ref`** — any branch or tag (default `main`). QA is how a feature branch gets seen before merge.
- **`reset_db`** — default **true**: the deploy drops every table and rebuilds the database from the deployed ref (#881). Untick it to keep user-entered QA data (threads, uploads, accounts) across the deploy — corpus rows are still re-synced from the ref either way (see below).

**One QA, last deploy wins.** There is a single shared environment, so a deploy replaces whatever ref was there before. A quick note in Slack before deploying a non-`main` ref is enough coordination. Per-PR preview environments are a later tier (#587).

## What a deploy does, in order

1. **Tests** — the full suite (`tests.yml`) runs against the ref; a red suite stops the deploy. (The old DigitalOcean path had no test gate; this one does.)
2. **Build & push** — the image from `docker/django/Dockerfile` is pushed to Docker Hub as `freelawproject/litigant-portal:<short-sha>-prod`.
3. **Secret re-sync** — the `litigant-env` ExternalSecret is forced to re-sync from AWS Secrets Manager, so pods read current values.
4. **Temp pod** — a throwaway pod (`temp-pod-<sha>`, label `app=litigant-deploy-temp`) starts on the new image with the real secrets. All state changes run here, _before_ the web pods are touched:
   - `collectstatic --noinput --clear`
   - with `reset_db`: scale `litigant-web` to 0, then drop every table in the schema
   - `migrate --noinput`
   - `sync_corpus --strict` (corpus YAML → database rows) and `bootstrap_superuser` — these two run on **every** deploy, with or without `reset_db`, so QA always serves the deployed ref's corpus
   - with `reset_db`: scale `litigant-web` back up
5. **Rollout** — `deployment/litigant-web` is set to the new image and the workflow waits for the rollout to go healthy.

**When migrations fail**, the deploy stops before the rollout and the temp pod is kept for debugging:

```bash
aws eks update-kubeconfig --region us-west-2 --name courtlistener
kubectl exec -it -n qa-litigant temp-pod-<sha> -- manage shell
```

It sleeps for an hour and is reaped at the start of the next deploy, so there is nothing to clean up by hand.

## What a deploy does NOT touch

- **docassemble.** It is a standing workload in the namespace, not part of this workflow — see below. Its state persisting across `litigant-web` deploys is a feature, not an accident.
- **Ingress and the access gate.** Routing (`/` → LP, `/interview/` → docassemble) and the pre-launch access gate (#885) are cluster config.
- **Secrets values.** The workflow re-syncs `litigant-env`; changing what's _in_ it (e.g. a new `DOCASSEMBLE_*` variable) means updating AWS Secrets Manager first — infra ask.

## The QA database is disposable

With `reset_db` on (the default) the database is rebuilt from scratch on every deploy: fresh migrations, corpus synced from the ref's YAML, a bootstrapped superuser, nothing else. Consequences worth knowing:

- Anything entered by hand on QA (threads, uploads, admin settings such as the chat model choice) is gone on the next default deploy. Demo data that must survive belongs in fixtures/corpus, not in the QA database.
- Runtime-stored settings reset on the same schedule — the reason #885 rejected a database-backed site password.
- `sync_corpus --strict` and `bootstrap_superuser` run on every deploy even with `reset_db` unticked. Unticking preserves user-entered rows, but corpus rows are always overwritten from the deployed ref's YAML — a corpus edit made directly in the QA database never survives a deploy.
- docassemble is unaffected: its state lives inside its own container and volumes, not in the LP database.

## docassemble on QA

Serving at `https://qa.litigantportal.com/interview/` since 2026-09-17 (#550): the all-in-one `jhpyle/docassemble` image, single replica, in live mode so devs author interviews directly on it. Path-routed under the LP hostname per the one-CNAME principle — never a subdomain.

Operational shape (full detail in [docassemble.md](./docassemble.md) and #550):

- **State is in persistent volumes** on `/usr/share/docassemble/backup` and `/files`. The container backs itself up on clean stop and nightly, and restores on boot; the 600s termination grace period exists so the shutdown backup can finish. A SIGKILL loses the delta and flags the next boot unsafe, which skips the restore (#701).
- **Admin credentials seed only into an empty database** (`DA_ADMIN_EMAIL` / `DA_ADMIN_PASSWORD` / `DA_ADMIN_API_KEY`, held in Bitwarden and the `docassemble-env` secret). After first boot they live in the backup volume; changing them via env is not a config change.
- **`POSTURLROOT=/interview/`** makes docassemble serve under the sub-path. Assets 404ing under `/interview/` means the prefix didn't take — recreate the pod so its init re-runs.

Post-change verification (from #550): the page loads over HTTPS; assets and links under `/interview/` don't 404; live updates don't hang (the WebSocket must pass the ingress); admin login works; and **a pod recreate keeps the playground and login** — that last check is what proves the volumes.

## Verifying a deploy

1. `https://qa.litigantportal.com/` loads and shows the deployed ref's UI.
2. Open the assistant and confirm a reply streams back (proves `AWS_BEARER_TOKEN_BEDROCK` and the SSE path).
3. A topic flow renders with its corpus content (proves `sync_corpus` ran).
4. `https://qa.litigantportal.com/interview/` still answers (proves the deploy didn't disturb docassemble).

## Current gaps (2026-09-18)

| Item                                                                                                                                                                                       | Issue |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- |
| LP → docassemble handoff config (`DOCASSEMBLE_BASE_URL` / `DOCASSEMBLE_PUBLIC_URL` / `DOCASSEMBLE_API_KEY` in `litigant-env`); until wired, the QA handoff opens the interview unprefilled | #908  |
| Access gate at the ingress covering `/api/` and `/interview/`, replacing `SitePasswordMiddleware`                                                                                          | #885  |
| docassemble URLs become validated settings instead of corpus-carried URLs                                                                                                                  | #879  |
| End-to-end QA verification sign-off (Jessica's #585 script for the ND flow)                                                                                                                | #587  |
