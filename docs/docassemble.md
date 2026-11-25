# docassemble — notes the code doesn't tell you

One page for the document-assembly side: authoring gotchas, local docassemble, QA hosting. The worked example lives in [`docassemble/nd-name-change/`](../docassemble/nd-name-change/) (interviews, form PDFs, branding, its own README). When stuck, check primary sources before guessing: [docassemble docs](https://docassemble.org/docs/documents.html) and the [jhpyle/docassemble](https://github.com/jhpyle/docassemble) source.

## Authoring gotchas (learned on #560)

- **`variable name:`, not `variable:`.** The wrong key is silently unrecognized; the block then fails as `No question type could be determined for this section`.
- **A standalone `attachment:` block needs `variable name:`.** A standalone _list_ of attachments is invalid — lists are only valid attached to a question. Multiple downloads on one screen = `attachments:` (plural) on a question.
- **The assembly loop.** Referencing an attachment's variable from the same question that defines it → `Infinite loop: <var> already looked for`. Define documents in standalone blocks, merge in a `code` block, let the final screen only link results.
- **`pdf_concatenate()`** takes the attachment's `DAFileCollection` directly (`petition_doc`, not `petition_doc.pdf`), returns a `DAFile`; download via `url_for(attachment=True)`. Not in the published docs — signature read from `docassemble/base/util.py`.
- **Map AcroForm fields by page + position, never by the name's apparent meaning.** Acrobat auto-names are ambiguous (`Text1`, `First name_2`) and these court forms label blanks _after_ the blank, so a field named `X` frequently fills the _next_ label's blank (the trailing-label shift). A name from nearby preprinted text can be a different blank entirely (the Confidential form's `State Of North Dakota` is the Case No line — leave it empty). Extract names + positions with `pdfminer.six` (walk `/Fields`, read `/Rect` + page).
- **Pin the form revision** (bundled Petition is "NC Pet/Rev. May 2024"). A court revising the form silently breaks the map — re-verify on revision.
- **Programmatic checks don't prove placement.** Zero-orphans/zero-unmapped cross-checks catch bad _names_; every placement bug survived them. Only filling the interview with `make interview-fill` and _reading the output PDF_ catches shifts and misassigned blanks.

## Local docassemble

`make docassemble-up` / `make docassemble-down` → http://localhost:8100. Deliberately outside LP's dev/prod compose profiles (~20 GB all-in-one image, opt-in; first pull takes minutes).

- Login is whatever `DA_ADMIN_EMAIL` / `DA_ADMIN_PASSWORD` seeded on the first boot (`docker-compose.docassemble.yml`, values from `.env`). docassemble's stock default does not reliably work. Those variables, and `DA_ADMIN_API_KEY` for the prefill client, seed **only into an empty database**: set them before the first `make docassemble-up`, or `down -v` and boot again.
- Port 8100 because LP's Caddy owns `:80` in dev; `DAHOSTNAME` must include the port or websockets and generated URLs break.
- Playground → **Utilities → "Get list of fields from a PDF or DOCX file"** reads an AcroForm PDF and scaffolds the `fields:` block — no manual field hunting.
- Playground work persists on named volumes across `down`/`up`.

### Test fills from the command line (#1197)

`scripts/interviews.py` uploads interviews to local docassemble and fills them with test personas, no browser needed. It reads `DA_ADMIN_API_KEY` (or `DOCASSEMBLE_API_KEY`, the same key under LP's name) and `DOCASSEMBLE_PUBLIC_URL` from `.env`.

```sh
make interview-sync                                  # upload new or changed files under docassemble/
make interview-sync ARGS="-n"                        # show what would upload
make interview-fill FOLDER=fc-eviction               # fill every persona in docassemble/fc-eviction/personas.yml
make interview-fill FOLDER=nd-name-change PERSONA=alex
```

- **Sync:** each folder under `docassemble/` becomes its own Playground project (`nd-name-change` → `ndnamechange`): `*.yml` to the interview editor, `*.pdf` to Templates, `*.css`/`*.svg` to Static. It uploads only what local docassemble lacks or what changed since the last upload (hashes in `~/.cache/lp-docassemble-sync.json`), so a `down -v` reset re-uploads everything.
- **Fill:** answers each screen from the persona's `answers` (the interview's own variable names) and writes to `build/interviews/<project>/`: the filled `<persona>.pdf`, an `-outlined.pdf` with every field boxed and named (red text, blue checkboxes), and PNGs of the outlined pages when poppler's `pdftoppm` is installed.
- **A persona missing an answer** stops the fill at that screen and names the variables it still wants. A yes/no checkbox needs an explicit `false`; a checkboxes field takes a map of choice to true/false.
- **Personas:** `fc-eviction` has Emily (landlord's attorney) and Marcus (no attorney, the other defenses); `nd-name-change` has Sandra (standard track, #311) and Alex (waiver track, #312). The two eviction personas fill every field on the Answer at least once.
- Sync puts interviews in the Playground only. The LP handoff still needs the package installed (below).

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

The corpus references name packages (`docassemble.ndnamechange`, `docassemble.fceviction`), so a Playground upload alone doesn't resolve them: each interview folder must be installed as its package on whichever docassemble serves the handoff. `deploy` does that from the repo, without the Playground (#556):

```sh
make interview-deploy FOLDER=fc-eviction                 # local docassemble
AWS_PROFILE=flp-root make interview-deploy FOLDER=fc-eviction TARGET=qa
```

- **Package:** the folder is zipped in the layout docassemble's own Package button produces: interviews in `data/questions/`, PDFs in `data/templates/`, CSS and SVG in `data/static/`, named `docassemble.<folder without dashes>`. Each build gets a new version, so pip always reinstalls.
- **Install:** the zip goes to the instance's `/api/package`, and the script waits on `/api/package_update_status` through the restart docassemble runs after every install, a few minutes. A failure exits with docassemble's own error. Re-installing replaces the package, including one installed by hand from the Playground.
- **Targets:** [`docassemble/targets.yml`](../docassemble/targets.yml) lists each instance's URL and the AWS Secrets Manager secret holding its `DA_ADMIN_API_KEY`. The key is read at deploy time with whatever AWS identity is active and never stored or typed. `DA_API_KEY` overrides it. `local` isn't listed: it reads the repo's `.env`.
- **AWS sign-in:** FLP's AWS uses IAM Identity Center. Once, run `aws configure sso` with start URL `https://freelawproject.awsapps.com/start`, SSO region `us-west-2`, session name `flp`, and name the profile after the account (`flp-root` for "Free Law Project (root)", which holds QA). After that, `aws sso login --sso-session flp` once a day covers every profile.
- **CI:** the `docassemble-deploy` workflow runs the same install from GitHub, separate from the web deploy: `gh workflow run docassemble-deploy.yml -f folder=fc-eviction -f target=qa`. It can't read QA's secret yet: the `litigant-deploy` user it signs in as needs `secretsmanager:GetSecretValue` on it, an infra grant.

Re-deploy after changing an interview: an installed package doesn't follow later edits to the repo or the Playground.
