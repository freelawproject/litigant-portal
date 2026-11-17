# Franklin County eviction — verified source notes (#607)

Compiled 2026-07-10 from the archived sources in this directory. Every fact
below carries its source; anything not listed here is NOT verified.

## Sources on file

| File | What it is |
|---|---|
| `orc-chapter-1923-forcible-entry-and-detainer-2026-07-10.md` | Full ORC Chapter 1923 text (codes.ohio.gov capture) |
| `fcmcclerk-evictions-faq-2026-07-10.md` | FCMC Clerk eviction FAQ (fcmcclerk.com/faq/civil/evictions) |
| `lasco-five-steps-of-eviction-process-2025-03.pdf` | LASCO tenant guide: 5 steps (rev. 3/2025) |
| `lasco-notice-to-leave-2023-11.pdf` | LASCO: Notice to Leave explained (rev. 11/2023) |
| `lasco-can-my-landlord-kick-me-out-2023-11.pdf` | LASCO: illegal lockout/self-help eviction (rev. 11/2023) |
| `lasco-second-cause-packet-rural-2024-02.pdf` | LASCO: Answer/counterclaim packet, 14pp (rev. 2/2024; RURAL-COUNTIES scoped — process facts are statewide, form samples may not match FCMC practice) |
| `lasco-eviction-dismissed-as-moot-2023-10.pdf` | LASCO: dismissal as moot after moving out (rev. 10/2023) |

LASCO = Legal Aid of Southeast and Central Ohio (NOT "Legal Aid Society of
Columbus"; scaffold header had it wrong). Helpline 1-888-246-4420, lasco.org,
apply at lasco.org/apply. Main office: 1108 City Park Ave Suite 200, Columbus
OH 43206, 614-221-7201.

## Verified statute facts (ORC 1923)

- **Notice to Leave: 3+ days before filing** (1923.04(A)). Written; served by
  certified mail return-receipt, in person, or left at the abode/premises.
  Mandatory conspicuous language: "You are being asked to leave the premises.
  If you do not leave, an eviction action may be initiated against you..."
- **Summons served at least 7 days before the hearing** (1923.06(A)).
  Mandatory summons language includes: no eviction in retaliation for lawful
  rights; continue depositing escrowed rent with the clerk; jury trial may be
  requested; right to seek legal aid.
- **Any defense may be asserted at trial** (1923.061(A)). In nonpayment
  cases the tenant may counterclaim (1923.061(B)); court may order rent paid
  into court; net-judgment offset can defeat the eviction if no rent remains
  due.
- **No-show = case tried anyway** (1923.07).
- **Continuances capped at 8 days** unless tenant posts bond (1923.08).
- **Set-out within 10 days of the writ of restitution** (1923.13/1923.14(A)).
  Appeal + stay + bond halts execution.
- 1923.02 covers who's subject; 1923.051 drug-offense restitution; 1923.062
  active-duty stay; 1923.12/.14(B) manufactured-home rules (out of MVP scope).

## Verified Franklin County Municipal Court facts (FCMC FAQ)

- **Hearings usually scheduled 14 to 21 days from filing.**
- Filing fees (landlord-side context): $128 single cause, $165 two causes.
- Service by bailiff or certified mail; set-outs arranged via service
  bailiff's office, (614) 645-7780.
- Court: 375 South High Street, Columbus OH 43215; (614) 645-8186.
- FAQ refers tenant-rights questions to Columbus Urban League (614) 257-6300.
- FCMC has a Self Help Center (FAQ refers "special matters" there).

## Verified tenant-guide facts (LASCO)

- Lockouts/utility shutoffs/put-belongings-outside are illegal self-help
  eviction; call law enforcement + attorney; out-of-pocket damages recoverable.
- Notice to Leave does not require moving; only a court can order removal.
  Offering rent within the 3-day window may resolve; after filing, landlord
  may also want filing costs.
- First cause = possession; second cause = money (back rent, utilities,
  damage). Separate hearings unless Answer+Counterclaim filed (1923.061(B)).
- **Answer / Answer+Counterclaim due within 28 days** of receiving the
  summons and complaint; weekend/holiday rolls to next business day. No
  Answer = default judgment for whatever the landlord claimed.
- Counterclaim grounds: overpaid rent, unreturned security deposit,
  repairs/improvements, injury from landlord's fault.
- Defense-helpful facts at the eviction hearing: no 3-day notice given; rent
  receipts; landlord accepted rent after notice; pattern of accepting late
  rent then refusing; tender refused; rent escrowed with clerk over
  conditions; third-party caused the late payment. Bad conditions alone are
  usually NOT a defense to nonpayment.
- Judgment: ask the judge how long you have to move; "Judgment Entry" is the
  written decision; writ of restitution → bailiff/sheriff set-out.
- Moved out before the hearing: return keys (get receipt or hand over before
  the judge), attend, ask for first-cause dismissal as moot; second cause
  survives and still needs an Answer within 28 days.

## Deadline candidates for fact_gather (the #621 rule: collect only what a page uses)

1. **Hearing date** (from the summons) — anchor; "your Answer to a second
   cause is due 28 days from the day you received court papers" is the
   stronger computed deadline:
2. **Date court papers received** → +28 days = Answer/Counterclaim deadline
   (1923.061(B) / Civ.R. timing per LASCO packet). Best ICS candidate.
3. Notice-date math (3 days) is landlord-side timing; probably info-only for
   tenants, not a gathered fact.

## Forms inventory (#610 docassemble packet)

From the FCMC Eviction Filing Process packet (`fcmc-eviction-process-packet.pdf`,
Rev. 07/2025) and the clerk's civil forms index (fcmcclerk.com/forms/civil):

**Landlord side:**
- Eviction Complaint: NOT court-provided ("legal supply store, law library or
  online"); must comply with RC 1923.04/1923.05. docassemble generates this.
- Notice to Leave the Premises: not court-provided either; mandatory bold
  conspicuous paragraph (text in packet + 1923.04). docassemble generates.
- Attachments required at filing: copy of the served Notice; **Local Rule
  9(G)**: copy of the written lease when the claim is founded on one; two
  extra copies of everything per defendant.
- CARES Act Compliance Affidavit (court form, archived:
  `fcmc-cares-act-compliance-affidavit.pdf`)
- Request for Set Out Form (court form, archived:
  `fcmc-request-for-set-out-form.pdf`; scanned image, needs OCR to read)
- Civil Military Affidavit (for default judgments):
  fcmcclerk.com/forms/civil
- **Pro se restriction: only the deeded property owner can sign/file without
  an attorney. Corporations, LLCs, and Trusts must have an attorney at all
  stages. No power-of-attorney representation.**

**Tenant side:**
- Answer / Answer & Counterclaims under 1923.061(B): LASCO packet pp. 9-14
  has the sample forms (checkbox denial reasons incl. ORC 5321.16 double
  security deposit; counterclaim grounds; proof of service block). Filing an
  Answer is free; a Counterclaim may carry a fee (Poverty Affidavit / FCMC
  Civil Fee Waiver Affidavit if unaffordable).
- Civil Blank Response/Motion Form (FCMC): fcmcclerk.com/forms/civil
- Application and Affidavit to Remove Eviction Record from Online Access
  (FCMC): fcmcclerk.com/forms/civil (post-case record relief; form not yet
  read, describe by title only)
- LASCO packet also documents the post-Answer flow: pretrial hearing, then
  possible mediation and final hearing.

## Fee discrepancy (unresolved)

- FCMC Eviction Filing Process packet (Rev. 07/2025): $123 single cause /
  $160 two causes.
- FCMC clerk FAQ (live page, captured 2026-07-10): $128 / $165.
- Corpus copy hedges with the FAQ numbers + "confirm with the clerk."

## Contacts (verified)

- FCMC Clerk Civil Division: 3rd floor, 375 South High Street; (614) 645-8186
  (clerk FAQ footer).
- Franklin County Municipal Court main "Contact Us": (614) 645-8214, 375 S.
  High St. (court site, pasted by Mitch 2026-07-10).
- FCMC Service Bailiff's Office: (614) 645-7780 (set outs).
- Columbus Bar Association Lawyer Referral Service: (614) 221-0754 (from the
  court's own filing packet).
- Columbus Urban League: (614) 257-6300 (tenant rights info, clerk FAQ).
- LASCO: 1-888-246-4420, lasco.org / lasco.org/apply.

## Still unverified / to check before merge

- FCMC Self Help Center: name, location, hours, phone (FAQ implies it exists;
  get specifics from fcmc.franklincountyohio.gov or the court site).
- Whether FCMC (urban) practice diverges from the rural-scoped LASCO packet's
  form samples (process facts are statute-based and hold).
- Rent escrow (ORC 5321.07) details if the defenses section references it.
- Columbus-specific rental assistance / mediation programs, if any get cited.
