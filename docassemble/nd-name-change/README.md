# ND adult name change — docassemble test packet

Versioned docassemble interviews and the court form they fill, so any dev can
reproduce the Topic Flow → document-assembly handoff fill locally. **Local bench
/ test material only** — not wired into LP's `dev`/`prod`, ships nothing to prod.

Each demo gets its own folder under `docassemble/` (form set + interviews +
README together), not split by file type.

## Contents

| File                    | What it is                                                                 |
| ----------------------- | -------------------------------------------------------------------------- |
| `petition.pdf`          | ND Petition for Name Change (NC Pet/Rev. May 2024) — the fillable template |
| `petition-standard.yml` | Interview for the standard **publish** track                               |
| `petition-waiver.yml`   | Interview for the **publication-waived** track                             |

Both interviews fill the **same** `petition.pdf`; they differ only at the
Petition's §11 (publish vs. waive + reason) and §12 (objections). The tracks fork
at entry, matching the Topic Flow corpus's standard/waiver split — no in-interview
branching.

## Test it locally

Prereq: the bench is up. See [`docs/docassemble-local-dev.md`](../../docs/docassemble-local-dev.md).

- Start the bench: `make docassemble-up`
- Open `http://localhost:8100` and log in (fresh box default: `admin@example.com` / `password`)
- Top-right menu → **Playground**
- Upload the template: in the Playground, open the **Templates** folder → upload `petition.pdf`
  (the `pdf template file: petition.pdf` line resolves against this folder)
- Upload the interview: in the **Sources** folder (the interview file list at the top of the
  editor) → upload `petition-standard.yml`, then select it so it loads in the editor
- Run it: click **Save and Run**
- Walk the 5 screens with the sample data below, then **download the filled Petition** at the end
- Verify on the PDF: every text field populated, and the right checkboxes ticked
  (§5 citizenship, §9 criminal history, §11 publication, §12 objections)
- Repeat with `petition-waiver.yml` to exercise the waiver track

Sample data:

```
Current name:     Jane Marie Doe
Requested name:   Jane Marie Smith
Residence:        123 Main St, Bismarck, Burleigh County, ND 58501
Resident since:   January 2025
Citizenship:      U.S. citizen
Criminal history: never convicted
Standard track — published: 2026-05-01, The Bismarck Tribune, Burleigh County
Waiver track   — reason:    victim of domestic violence
```

For answer sets tied to real user stories, see [`test-personas.md`](test-personas.md)
(e.g. Sandra, post-divorce restoration — #311).

## Branding & demo polish (#549)

For court-partner demos the interview is styled to read as Litigant Portal and
dead/stock affordances are removed. Versioned here:

- `lp-branding.css` — LP palette + type mapped onto docassemble's Bootstrap
  (parity, not a design-system port).
- `lp-logo.svg` — LP logo for the navbar.

Apply on the bench (Playground):

1. Upload `lp-branding.css` and `lp-logo.svg` to the project's **Static** folder.
   Both interviews already reference the CSS via `features: css: lp-branding.css`.
2. End screen is **download-only** — `allow emailing: False` is set in both
   interviews (email delivery isn't wired and is deferred to v2, #441; no SMS).
3. Server → **Configuration** for the global brand + clean anonymous entry
   (verify exact key names on the bench — docassemble's config docs weren't
   reachable when this was drafted):
   - `brandname: Litigant Portal`
   - `show login: False` — no login wall for an anonymous litigant
   - `default interview:` the published interview, so root isn't the demo list
   - restrict/hide the sample "demo" interviews for anonymous visitors

Still deferred (bigger lifts, not branding-CSS): publishing the interviews as a
package for a clean anonymous URL (vs Playground), shipping the Inter woff2 for
exact type parity, and a deeper atomic-design match.

## Field mapping

The interviews map answers to the Petition's real AcroForm field names (extracted
and verified against page/position; all checkbox "on" states are `Yes`). Source
field names are Acrobat auto-generated and ambiguous (`Check Box1`..`11`,
duplicated `First name`), so the mapping is position-verified, not name-obvious —
re-verify whenever the court revises the form. Concrete gotcha: in §3 the
parenthetical labels trail the blank they describe, so the field names are
shifted one slot — `Petitioner currently resides at`/`address`/`city`/`North
Dakota` actually hold address/city/county/zip.

## Related

- Handoff epic: #531 (under document-assembly #123)
- Court-partner PDF requirements and the fill-strategy decision (AcroForm vs flat
  overlay) are tracked under #123.
- The DV waiver reason on the form still cites the repealed § 14-07.1-01; the
  form-text correction is tracked on #495 (the interview only checks the box, so
  it is unaffected).
