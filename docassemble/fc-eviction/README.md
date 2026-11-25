# Franklin County eviction — docassemble interview

The tenant's Answer for Franklin County Municipal Court, so any dev can
reproduce the Topic Flow → docassemble handoff fill locally (#610).

## Contents

| File              | What it is                                                                        |
| ----------------- | --------------------------------------------------------------------------------- |
| `answer.pdf`      | Answer of Defendant(s), "Rev. December 2021", made fillable (37 fields)           |
| `answer.yml`      | Interview that fills it, prefilled from the tenant's confirmed answers            |
| `lp-branding.css` | Litigant Portal look on docassemble (copy of `../nd-name-change/lp-branding.css`) |

## Where the fillable PDF comes from

The Self Help Center's forms are flat PDFs. `scripts/fc_eviction_fillable.py`
adds the fields: FormFyxer found the blanks once, and the script keeps those
positions under names read off the page (`plaintiff_landlord`,
`defense_paid_in_full`, `landlord_attorney_address_line_1`). It writes this
folder's `answer.pdf` and the corpus copy at
`litigant_portal/corpus/forms/fc-eviction-answer.pdf`. Its docstring has the
setup. Rerun it when the court revises the form, then run `make interview-fill` again.

The field names describe what the blank holds, so the trailing-label shift that
North Dakota's Acrobat names have (`../nd-name-change/README.md`) doesn't apply.

## Test it locally

Same local docassemble as North Dakota: see [`docs/docassemble.md`](../../docs/docassemble.md)
and the steps in [`../nd-name-change/README.md`](../nd-name-change/README.md#test-it-locally).
Upload `answer.pdf` to **Templates**, `lp-branding.css` to **Static**, and
`answer.yml` as the interview, then **Save and Run**.

Sample answers (Emily, a tenant with a hearing tomorrow):

```
Case number:      2026 CVG 012345
Landlord:         Riverside Commons LLC
Judge:            (blank)
Tenant:           Emily Ann Carter, 123 Main St Apt 4, Columbus, OH 43215, 614-555-0100
Defenses:         paid in part ($450.00); security deposit not credited ($800.00)
Landlord attorney: Jane Roe, 456 Broad St, Columbus, OH 43215
Mailed:           (blank)
```

Check on the PDF: the caption, the two checked defenses with their amounts,
the signature block, and the attorney's box under Proof of Service with the
landlord's box empty. Then tab through the downloaded file: the fields stay
editable.
