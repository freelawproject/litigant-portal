# docassemble — notes the code doesn't tell you

One page for the document-assembly side: authoring gotchas, the local bench, QA hosting. The worked example lives in [`docassemble/nd-name-change/`](../docassemble/nd-name-change/) (interviews, form PDFs, branding, its own README). When stuck, check primary sources before guessing: [docassemble docs](https://docassemble.org/docs/documents.html) and the [jhpyle/docassemble](https://github.com/jhpyle/docassemble) source.

## Authoring gotchas (learned on #560)

- **`variable name:`, not `variable:`.** The wrong key is silently unrecognized; the block then fails as `No question type could be determined for this section`.
- **A standalone `attachment:` block needs `variable name:`.** A standalone _list_ of attachments is invalid — lists are only valid attached to a question. Multiple downloads on one screen = `attachments:` (plural) on a question.
- **The assembly loop.** Referencing an attachment's variable from the same question that defines it → `Infinite loop: <var> already looked for`. Define documents in standalone blocks, merge in a `code` block, let the final screen only link results.
- **`pdf_concatenate()`** takes the attachment's `DAFileCollection` directly (`petition_doc`, not `petition_doc.pdf`), returns a `DAFile`; download via `url_for(attachment=True)`. Not in the published docs — signature read from `docassemble/base/util.py`.
- **Map AcroForm fields by page + position, never by the name's apparent meaning.** Acrobat auto-names are ambiguous (`Text1`, `First name_2`) and these court forms label blanks _after_ the blank, so a field named `X` frequently fills the _next_ label's blank (the trailing-label shift). A name from nearby preprinted text can be a different blank entirely (the Confidential form's `State Of North Dakota` is the Case No line — leave it empty). Extract names + positions with `pdfminer.six` (walk `/Fields`, read `/Rect` + page).
- **Pin the form revision** (bundled Petition is "NC Pet/Rev. May 2024"). A court revising the form silently breaks the map — re-verify on revision.
- **Programmatic checks don't prove placement.** Zero-orphans/zero-unmapped cross-checks catch bad _names_; every placement bug survived them. Only bench-filling the interview and _reading the output PDF_ catches shifts and misassigned blanks.

## Local bench

`make docassemble-up` / `make docassemble-down` → http://localhost:8100. Deliberately outside LP's dev/prod compose profiles (~20 GB all-in-one image, opt-in; first pull takes minutes).

- Login is whatever `DA_ADMIN_EMAIL` / `DA_ADMIN_PASSWORD` seeded on the first boot (`docker-compose.docassemble.yml`, values from `.env`). docassemble's stock default does not reliably work. Those variables, and `DA_ADMIN_API_KEY` for the prefill client, seed **only into an empty database**: set them before the first `make docassemble-up`, or `down -v` and boot again.
- Port 8100 because LP's Caddy owns `:80` in dev; `DAHOSTNAME` must include the port or websockets and generated URLs break.
- Playground → **Utilities → "Get list of fields from a PDF or DOCX file"** reads an AcroForm PDF and scaffolds the `fields:` block — no manual field hunting.
- Playground work persists on named volumes across `down`/`up`.

## QA hosting (EKS, path-routed under the LP hostname)

docassemble serves at `https://qa.litigantportal.com/interview/` — path, not subdomain, so a partner needs one CNAME (see Deployment principles under [Production](../README.md#production)). Since 2026-09-17 (#550) it's a standing workload in the `qa-litigant` EKS namespace: the all-in-one `jhpyle/docassemble` image (its own Postgres, Redis, RabbitMQ under supervisor), single replica because the database is inside the container, in **live mode** — devs log in and author interviews directly on it. The manifests and secrets live with the infra team, outside this repo (`qa-litigant/5_docassemble.yml` and friends; AWS Secrets Manager `k8s/qa-litigant/docassemble-env`). LP deploys never touch it — see [qa-deploy.md](./qa-deploy.md) — so interviews and accounts persist across `litigant-web` rollouts by design.

**State lives in two persistent volumes**, not in the image: `/usr/share/docassemble/backup` and `/usr/share/docassemble/files`. docassemble keeps everything internally (playground files, server config, user accounts), and its `initialize.sh` writes a full backup on clean stop and nightly by cron, restoring from it on boot. That backup volume is what makes a pod recreate safe. `terminationGracePeriodSeconds: 600` (the compose `stop_grace_period` equivalent) gives the shutdown backup time to finish: a SIGKILL loses the delta and flags the next boot as an unsafe shutdown, which skips the restore (#701).

Gotchas the manifests don't explain:

- **Admin credentials seed only into an empty database.** `DA_ADMIN_EMAIL` / `DA_ADMIN_PASSWORD` / `DA_ADMIN_API_KEY` (Bitwarden, Litigant Portal collection) applied on first boot only; afterwards the accounts live in the backup volume and env changes are ignored. A fresh instance booted _without_ them gets docassemble's public default login — rotate it immediately.
- **`POSTURLROOT=/interview/`** makes docassemble regenerate its internal nginx for the sub-path. Assets/links 404 under `/interview/` → the prefix didn't take; recreate the pod so `initialize.sh` re-runs.
- **The ingress must preserve the `/interview/` prefix** (not strip it) and pass the WebSocket upgrade through, or live interview updates hang. Test this first after any routing change.
- **`USEHTTPS=false` + `BEHINDHTTPSLOADBALANCER=true`**: the ingress terminates TLS and forwards plain HTTP; docassemble still builds `https://` URLs and secure cookies.
- **`DAHOSTNAME` is a bare hostname, no scheme** (`qa.litigantportal.com`). A `https://` prefix produces `https://https://…` URLs and broken cookies.
- **≥ 4 GB RAM** — docassemble idles ~2 GB and OOMs below that. First boot pulls the ~20 GB image and inits its own DB: 15+ minutes observed on EKS.
- **Playground empty or default admin login after a recreate** = the volumes weren't mounted, or an unsafe shutdown skipped the restore. Confirm the PVCs are bound before re-uploading anything by hand; if they are, a recreate with the mounts restores them.

**The DigitalOcean box is dev now, not QA** (#880): the same shape in compose form, documented in [deploy/qa-do/README.md](../deploy/qa-do/README.md), removed entirely at the #461 cutover.

**Production currently runs a copy of this QA setup, and that is a placeholder, not the launch configuration.** QA is deliberately open for editing: devs log in, change interviews in place, and use the Playground. A production instance serving litigants must be the opposite — no login screen, anonymous sessions only, and interviews served exclusively from installed packages, never the Playground. That lockdown work is tracked in #556; how docassemble is hosted per court partner is a separate open decision (#888).

One requirement holds for every environment, QA, prod, or a future court instance: the `/usr/share/docassemble/backup` mount must be persistent storage. Skip it and the first pod recreate silently erases every interview, account, and setting (that is what happened in #701).

## Topic Flow → docassemble handoff contract

Two systems, two jobs, one contract — with a deliberate split of which facts each side owns:

- **Topic Flow owns** a light fact set, named for the glossary (`first_name`, `county`, `name_change_publication_date`), and hands it over on the way out.
- **The interview owns** the full document fact set Topic Flow never collects (residence, residency-since, citizenship, criminal history, publication newspaper, track-specific fields). Asking those in the guided flow would duplicate the interview.

**The corpus names the interview; the environment names the host (#879).** A flow's packet section carries `interview_reference`, a docassemble package reference the loader validates (`docassemble.<package>:data/questions/<file>.yml`, never a URL). Where it is sent comes from settings alone: `DOCASSEMBLE_BASE_URL` is the API root LP calls (and the default launch base), `DOCASSEMBLE_PUBLIC_URL` the litigant-facing base when those differ, `DOCASSEMBLE_API_KEY` turns prefill on. With neither URL set, the packet renders without the interview button and the registry logs which flows are affected; a key without `DOCASSEMBLE_BASE_URL` beside it is a startup warning (`docassemble.W001`), since prefill would silently fall back to the plain interview on every handoff. This keeps author-controlled content from ever deciding where the API key and the litigant's answers go.

**The names are not 1:1, and the mapping is explicit.** Only 3 of the interview's 19 variables happen to share our glossary names, so each flow's packet section carries an `interview_prefill` map from question id to interview variable, next to `interview_reference`:

```yaml
interview_reference: 'docassemble.ndnamechange:data/questions/petition-standard.yml'
interview_prefill:
  first_name: current_first
  county: residence_county
```

**The full `data/questions/` path is required — the schema rejects the short alias.** docassemble's API accepts the alias (`docassemble.pkg:file.yml`) and creates a session under it, but the browser-side launch canonicalizes to the `data/questions/` path and then cannot find that session — the litigant lands on "Unable to locate interview session" and an empty, unprefilled interview. Learned the hard way on #879, so the loader now refuses an aliased reference at startup instead of shipping it.

The schema validates every key is a `fact_gather` question id of that flow and every value is a plain Python identifier (docassemble executes these as assignment statements, so they may only come from author-controlled YAML). A drift guard in the test suite parses the versioned interviews and fails when a mapped variable no longer exists there.

Names stay structured first / middle / last, never a single free-text field — splitting a combined string back apart is lossy.

Three rules the prefill runs on:

- **Only reviewed answers are sent.** A preset variable skips its question, so docassemble never asks the litigant to confirm it and there is no write-back. Confirmation has to happen on our side first.
- **A preset variable skips its validation too.** A value outside a field's declared choices is never caught and prints straight onto the court form, which is why the drift guard also compares choice value sets.
- **`waiver_reasons` is never mapped.** It's a `checkboxes` field, so prefilling it needs a DADict object encoding; the interview re-asks that one question. It is also the sensitive one (domestic violence), which is no loss to leave uncollected.

Sending the payload creates a session, so the handoff is a POST from a form, not a link, and it falls back to the plain unprefilled launch URL (built from the same settings) whenever no API key is configured or the API call fails. Deleting the session once its packet is downloaded is tracked on #805.

## Serving the handoff: the interviews must be installed as a package

The corpus references name the `docassemble.ndnamechange` package, so a Playground upload alone no longer resolves them: the interviews must be installed as that package on whichever docassemble serves the handoff (bench or QA). From the Playground it takes a minute:

1. Upload the interviews to **Sources** and the PDFs to **Templates** (the "Test it locally" steps in [`docassemble/nd-name-change/README.md`](../docassemble/nd-name-change/README.md)).
2. **Folders → Packages** → add a package named `ndnamechange`, attach both interview files and the five PDF templates.
3. Click **Install**. The server now resolves `docassemble.ndnamechange:data/questions/petition-standard.yml` for every user, and the LP handoff works.

Re-run the Install after changing an interview: the Playground copy and the installed package are separate copies.
