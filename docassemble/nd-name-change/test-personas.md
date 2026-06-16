# Test personas — ND name-change interviews

Concrete answer sets for running the interviews in the bench Playground. Each is
tied to a Litigant Portal user story so the test data stays grounded in a real
scenario. Values the story doesn't specify are filled plausibly and marked `*`.

## Sandra — post-divorce name restoration (#311)

**Track:** standard publish (`petition-standard.yml`). Sandra is restoring her
full birth surname, not just a first/middle name, so she does **not** qualify for
the publication waiver.

- **Screen 1 — Your current legal name**
  - First: `Sandra`
  - Middle: `Marie` \*
  - Last: `Larson` \* (married surname — the story gives only her birth name)
- **Screen 2 — The name you want**
  - First: `Sandra`
  - Middle: `Marie` \*
  - Last: `Eriksen` (her birth name, from the story)
- **Screen 3 — Where you live**
  - Street: `1420 Cottonwood Lane` \*
  - City: `Bismarck`
  - County: `Burleigh`
  - ZIP: `58503` \*
  - Resident since: `June 2008` \* (long-time Bismarck resident)
- **Screen 4 — A few details**
  - Citizenship: `U.S. citizen`
  - Criminal history: `never convicted`
- **Screen 5 — Publication**
  - Published on: `2026-06-01` \*
  - Newspaper: `The Bismarck Tribune`
  - County: `Burleigh` (defaults from residence)

Expected page-4 block: "from Sandra Marie Larson / to Sandra Marie Eriksen."
Because Sandra has a middle name, this run also confirms the caption renders with
single spacing (`Sandra Marie Larson`, not a double gap).
