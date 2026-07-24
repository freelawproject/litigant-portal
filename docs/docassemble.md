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

- Default login `admin@admin.com` / `password` — a well-known docassemble default, change it immediately.
- Port 8100 because LP's Caddy owns `:80` in dev; `DAHOSTNAME` must include the port or websockets and generated URLs break.
- Playground → **Utilities → "Get list of fields from a PDF or DOCX file"** reads an AcroForm PDF and scaffolds the `fields:` block — no manual field hunting.
- Playground work persists on named volumes across `down`/`up`.

## QA hosting (path-routed under the LP hostname)

docassemble serves at `/interview/` on the existing LP hostname — path, not subdomain, so a partner needs one CNAME (see Deployment principles under [Production](../README.md#production)). The QA-only compose override (`docker-compose.docassemble.qa.yml`) joins docassemble to the LP network (Caddy reaches `docassemble:80`, no public port); the route is `docker/caddy/conf.d/docassemble.caddy`. A base-only prod deploy loads none of it. State persists across deploys, and `down -v` is fenced off docassemble's volumes (#701).

Gotchas the compose files don't explain:

- **`POSTURLROOT=/interview/`** makes docassemble regenerate its internal nginx for the sub-path. Assets/links 404 under `/interview/` → the prefix didn't take; recreate the container so `initialize.sh` re-runs.
- **Live updates hang** = the WebSocket isn't threading the prefix. Verify `POSTURLROOT` took and Caddy is upgrading the socket — test this first after any deploy change.
- **`BEHINDHTTPSLOADBALANCER=true`**: Caddy terminates TLS and forwards plain HTTP; docassemble still builds `https://` URLs and secure cookies.
- **`DA_HOSTNAME` is a bare hostname, no scheme** (`qa.litigantportal.com`, unlike `DOMAIN`). A `https://` prefix produces `https://https://…` URLs and broken cookies; unset, compose substitutes an empty string with only a warning and docassemble runs hostnameless.
- **≥ 4 GB RAM** — docassemble idles ~2 GB and OOMs on a 2 GB box. First boot inits its own DB: 5–10 minutes.
- **Don't run the bench and QA container on the same box** — stop `docassemble-dev` first.

docassemble's real production home rides the CL infra move (#461); QA hosting is the interim demo host.

## Topic Flow → docassemble handoff contract

Two systems, two jobs, one contract — with a deliberate split of which facts each side owns:

- **Topic Flow owns** a light fact set, named 1:1 to the interview's variables so a future prefill is lossless: `current_first` · `current_middle` · `current_last` · `requested_first` · `requested_middle` (· `requested_last`, standard track only) · `filing_county` · `publication_date`. Today it collects only what a page actually uses (#621); the rest return when prefill (#531) gives them a consumer.
- **The interview owns** the full document fact set Topic Flow never collects (residence, residency-since, citizenship, criminal history, publication newspaper, track-specific fields). Asking those in the AI-free flow would duplicate the interview.

Names stay structured first / middle / last, never a single free-text field — splitting a combined string back apart is lossy. **v1 is link-out + manual return, no prefill** (#543): the prefill seam (POSTing the answer set to start a session, PII out of the URL) is deferred v2 (#531), with the Briefcase (#177) as its natural carrier. Same ids, no rework, makes that future a drop-in.
