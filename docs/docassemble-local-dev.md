# docassemble — local dev bench

A standalone local docassemble instance for authoring and testing the Topic Flow
→ document-assembly interviews. **Local dev only** — real hosting waits for the
infra-team move. It is intentionally _not_ part of LP's `dev`/`prod` compose
profiles: docassemble is a ~20 GB all-in-one container, so it's opt-in for anyone
working on the handoff.

Part of the docassemble handoff epic (under #123). Config grounded in
[docassemble's docker docs](https://docassemble.org/docs/docker.html).

## Run it

```sh
make docassemble-up      # docker compose -f docker-compose.docassemble.yml up -d
# first run pulls ~20 GB — give it a few minutes, then watch logs:
docker logs -f docassemble-dev
```

Open **http://localhost:8100** once the logs settle.

- Default login: `admin@admin.com` / `password` — **change the email and password
  immediately** (User List → Edit). docassemble ships with this well-known default.
- Port is `8100` because LP's Caddy already owns `:80` in dev. `DAHOSTNAME` is set
  to `localhost:8100` (the port must be included) so websockets and generated URLs
  resolve. No separate websockets port is needed for local access.

```sh
make docassemble-down    # stop (named volumes persist Playground work across down/up)
```

## Extract a form's fillable fields (the immediate task)

docassemble's Playground reads a fillable PDF's AcroForm field names and scaffolds
the interview for you — no manual field hunting.

1. Log in → **Playground**.
2. **Utilities** (top menu) → "Get list of fields from a PDF or DOCX file".
3. Upload the form PDF (start with the ND `Petition for Name Change`, confirmed
   tab-fillable). docassemble lists every AcroForm field name and emits a starter
   `fields:` block + a sample interview.
4. Hand that field list back — it's the mapping target for the interview's
   `attachment` block.

## How the interview is structured

`question`/`fields` blocks collect the data (reusing the Topic Flow corpus's data
points — current name, requested name, county — plus per-form extras the Petition
needs: residency-since date, citizenship, criminal-history flag, publication/waiver
choice). An `attachment` block then maps each AcroForm field name to a value:

```yaml
mandatory: True
attachment:
  pdf template file: petition.pdf
  fields:
    - '<acroform field name>': ${ requested_full_name }
    - '<acroform field name>': ${ filing_county }
```

## Notes

- The current Petition (NC Pet/Rev. May 2024) still cites the repealed
  § 14-07.1-01 for the domestic-violence waiver reason — interview copy and the
  corpus content must reflect the corrected reference (tracked on #495).
- Persistence: Playground work and the auto-DB-backup live on named volumes; if a
  `down`/`up` ever loses state, verify the backup-restore on startup.
