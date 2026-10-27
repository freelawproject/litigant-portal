# Portsmouth (VA) sources

- **Received:** 2026-10-26, from Mitch.
- **Court:** Portsmouth General District Court, hosted by its Clerk's Office. Court pages: the [Virginia Judicial System's](https://vacourts.gov/courts/gd/portsmouth/home) and the [City of Portsmouth's](https://www.portsmouthva.gov/general-district-court).
- **Letter of intent:** `_local/` (not tracked) holds the court's letter of intent to Free Law Project, signed by the Chief Judge and the Clerk of Court.
- **Seal:** `branding/Seal_of_Virginia.svg`. The general district court uses the state seal. `litigant_portal/corpus/courts/portsmouth-va/branding/logo.png` is rendered from it at 256×256: `magick -background none -density 300 Seal_of_Virginia.svg -resize 256x256 -strip PNG32:logo.png`.

## From the letter of intent

- **Who it serves:** low-income self-represented defendants in unlawful detainer (eviction) and warrant in debt cases; tenants seeking redress for lease or habitability violations; people seeking protective orders.
- **Initial topics and forms:**
  - Grounds of Defense (DC-442): defending a warrant in debt or unlawful detainer. Defenses not listed on it can be foreclosed at trial.
  - Tenant's Assertion (DC-429): relief from poor living conditions.
  - Protective Order (DC-383).
- **The court:** general jurisdiction for misdemeanors and civil claims up to $50,000 in the city of Portsmouth; over 22,000 civil cases filed in 2025. Acts as a small claims court for self-represented litigants.
- **Filing:** paper only. General district courts in Virginia have no e-filing yet; a PDF-by-email portal like one other Virginia GDC uses is a possible path.
- **Partners named:** the Forms and E-filing Subcommittee of the Virginia Access to Justice Commission's Self-represented Litigants Committee. Norfolk GDC and the Virginia Beach Juvenile and Domestic Relations Court may join later.

## Notes

- The letter is dated May 1, 2016, which reads as a typo for 2026: it cites a 2025 survey and 2025 case counts.
- No topics in the corpus yet (#1100). `jurisdiction_level` is left blank until it's confirmed.
