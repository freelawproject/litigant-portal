# Corpus source documents (local archive)

Local archive of the **source material** court partners give us — official forms,
instruction guides, and feedback — that backs the Topic Flow corpus in
`litigant_portal/content/`.

**These files are gitignored on purpose.** Everything under `corpus-sources/`
except this README is excluded from version control:

- The durable source of truth will be an internal wiki, not this repo.
- They are the partner's documents (often large binaries), not our code.
- Court partners deliver them by uploading to a shared Google Drive; this
  directory is our local working archive of those uploads.

## Structure

Mirror the corpus keys — one directory per court, then per topic:

```
corpus-sources/
  <court-slug>/            # matches metadata.court, e.g. north-dakota
    <topic-slug>/          # matches the topic, e.g. adult-name-change
      *.docx, *.pdf …      # the files exactly as the partner delivered them
      SOURCE.md            # optional: Drive link, date received, who uploaded
```

Example:

```
corpus-sources/north-dakota/adult-name-change/
  Instructions for a name change adult.docx
  Petition name change adult.docx
  …
```

## Using it

1. Drop the partner's uploaded files under the right `<court>/<topic>/`.
2. Author or correct the corpus in `litigant_portal/content/` against them.
3. Note provenance (a `SOURCE.md` with the Drive link + date) so a later reader
   knows where a batch came from and how current it is.
