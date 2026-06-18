# docassemble interview authoring — gotchas & patterns

Hard-won lessons from building the ND adult name-change packet ([#560](https://github.com/freelawproject/litigant-portal/issues/560)). Most of these cost real bench cycles; the framework docs and source settle them, so **check the primary sources before guessing** (see the bottom of this page).

This is a reference, not a tutorial. For running the local bench see [`docassemble-local-dev.md`](docassemble-local-dev.md); for QA hosting see [`docassemble-qa-hosting.md`](docassemble-qa-hosting.md). The worked example is [`docassemble/nd-name-change/petition-standard.yml`](../docassemble/nd-name-change/petition-standard.yml).

## Interview block structure

- **The key is `variable name:`, not `variable:`.** The wrong key is silently unrecognized, and docassemble then can't resolve the block — it fails with `No question type could be determined for this section`. That error usually means "this block has no recognized directive," and a misspelled `variable name` is one way to trigger it.

- **A standalone attachment block needs `variable name:`.** An `attachment:` block is valid outside a question _only_ when it carries `variable name:` (which defines the document, assembled on demand). A standalone block written as a **list** of attachments (`attachment:` with `- ` items) is **not** valid — a list of attachments is only valid when attached to a question.

- **Multiple downloads on one screen** = `attachments:` (plural, a list) **on a question**. Each list item may carry its own `variable name:`.

- **The assembly loop.** Referencing an attachment's variable (e.g. in a combined-PDF link, or `pdf_concatenate`) from the **same question that defines that attachment** causes an infinite loop: `Infinite loop: <var> already looked for`. The screen seeks a variable it is itself mid-assembling. **Fix: define the documents separately from the screen that uses them** — standalone `attachment` blocks define each doc, a `code` block merges them, and the final screen only links to the results.

## Combining filled PDFs into one file

`pdf_concatenate()` (in `docassemble.base.util`) merges PDFs:

```yaml
code: |
  packet_pdf = pdf_concatenate(
      petition_doc, notice_doc, confidential_doc, order_doc,
      filename="nd-name-change-packet.pdf")
```

- It accepts the attachment's `DAFileCollection` variable **directly** — pass `petition_doc`, not `petition_doc.pdf` (its `get_pdf_paths` pulls `.pdf` off the collection). It also accepts `DAFile`, `DAFileList`, `DAStaticFile`, and path strings.
- It returns a `DAFile`. Make it downloadable with `${ packet_pdf.url_for(attachment=True) }`.
- For an individual form's PDF, the collection exposes it as `${ petition_doc.pdf.url_for(attachment=True) }`.

This function is **not** in the published docs pages (documents.html / functions.html); the signature above was read from source (see below).

## Mapping AcroForm fields

The interview's `attachment` `fields:` map answers to the form PDF's real AcroForm field names. These ND forms make that error-prone:

- **Auto-generated names are ambiguous.** Acrobat names blanks `Text1`, `1`, `undefined`, and duplicates (`First name`, `First name_2`, …). **Map by page + position, never by the name's apparent meaning.** Extract names + positions with `pdfminer.six` (walk the AcroForm `/Fields`, read each widget's `/Rect` and page).

- **Trailing-label shift.** These forms print a blank's label _after/below_ the blank, so the auto-name is offset by one slot from the blank it actually fills. Seen in the Petition §3 residence line (the names `Petitioner currently resides at` / `address` / `city` / `North Dakota` actually hold address / city / county / zip) and in the Confidential form's signature block (name / address / city / phone all sat one row low). A field named `X` frequently fills the blank belonging to the _next_ label.

- **A name from nearby text can be a different blank.** The Confidential form's field auto-named `State Of North Dakota` is positionally the **Case No** line (the state is preprinted) — it must be left empty, not set to "North Dakota".

- **Pin the form version.** The map is tied to one revision (the bundled Petition is "NC Pet/Rev. May 2024"). A court revising the form silently breaks the map — re-verify on revision.

## Verifying a fill — the loop that actually catches bugs

1. Extract field names + page positions (`pdfminer.six`).
2. Map by page/position against the legal text; cross-check **zero orphans** (every key matches a real field) and **zero unmapped** fields programmatically.
3. **Bench-fill** the interview with sample data and **read the output PDF.**

Step 2 proves the field _names_ are right. It does **not** prove _placement_ — only the bench fill + reading the filled PDF catches the trailing-label shifts and misassigned blanks. Every placement bug in this packet survived the programmatic check and was caught only by reading the filled PDF.

## Primary sources

- docassemble document assembly & attachments — [docassemble.org/docs/documents.html](https://docassemble.org/docs/documents.html)
- `pdf_concatenate` implementation — `docassemble/base/util.py` in [jhpyle/docassemble](https://github.com/jhpyle/docassemble) (`def pdf_concatenate(*pargs, **kwargs)`)
- Field rendering / attachment markup — `docassemble/base/standardformatter.py` (same repo); the Download/Preview controls are Bootstrap nav-tabs (`.da-attachment-tablist .nav-link`), which is why branding CSS has to target them.
