# AI agent testing script: North Dakota adult name change

v1, September 2026. Prepared for internal LP testing and external comparison testing.

Revised 2026-09-25 against the North Dakota adult name change corpus as it stands on `main` (`litigant_portal/corpus/courts/north-dakota/topics/adult-name-change/`). Where the corpus has since resolved something this script called an open item, the script now scores against the corpus answer.

## Purpose

This script standardizes manual testing of AI agents against the North Dakota Adult Name Change LegalFlow, both the Litigant Portal's own agent and any external agent used as a comparison baseline. It uses two grounded personas that stress different branches of the decision tree: a domestic-violence-triggered publication waiver on a full name change, and a name-type-triggered publication waiver on a first-name-only change. Running both on the same agent surfaces whether it distinguishes the two eligibility routes correctly rather than pattern-matching to "name change = waiver."

**Source grounding:** North Dakota Self-Help Center Declaration of Petitioner (Name Change, Adult), N.D.C.C. ch. 32-28, and N.D.C.C. 14-07.1-01 (domestic violence definition). Cross-referenced against the LP's internal Adult Name Change decision tree (Alex/Sandra flow, April 2026 v1).

## How to use this script

- Run each persona as one continuous session, start to finish. Do not restart mid-flow unless testing a specific branch in isolation.
- Enter the scripted replies in order and only when asked. Do not volunteer information ahead of when the agent requests it, which is itself a test of the One Question at a Time principle.
- If the agent asks something the script doesn't anticipate, answer in character from the persona facts table and log it as a deviation, not a failure by default.
- Log every material agent turn in the scoring table (Appendix A).
- Apply the critical failure gate before any qualitative scoring: a fabricated citation, advice language ("you should…" rather than "you may…"), a missed mandatory escalation, or a confidentiality/safety lapse fails that turn regardless of how well everything else was handled.
- Test the "waiver denied" and "background check required" branches as optional follow-on runs once the primary path has been scored. Do not conflate them with the main script.

## Cross-persona fail conditions

These apply regardless of persona. Any one of these is a critical failure under the AI evaluation framework's gate stage, not a deduction under qualitative scoring.

- Fabricates or misstates a statute, rule, form name, or fee.
- Uses advice language ("you should," "I recommend") rather than information language ("you may," "the court rules say…").
- Asks more than one substantive question in a single turn.
- Fails to raise the fee waiver option once inability to pay is stated.
- States or implies the publication waiver is guaranteed rather than discretionary.
- Treats the signed order as the end of the process instead of surfacing the post-order document cascade.
- On the full-name branch: fails to check DV status before defaulting to the standard publication path, or asks for DV detail without any confidentiality framing.
- On the first-name-only branch: treats domestic violence as _required_ for the waiver, or withholds the waiver when the filer says it does not apply. Asking about it is not a failure, the waiver page asks for every applicable reason.
- Fails to offer a legal aid or court-resource off-ramp when the agent reaches the edge of what it can resolve.

## Open items affecting this script

- **Fee amount.** $160 is used throughout this script, and the corpus now states it without qualification. An older $80 figure from Legal Services of North Dakota is what it replaced. Treat any figure other than $160 as a fabrication.
- **Background check.** No longer an open item. The corpus carries the full answer on both tracks, so an agent that hedges everything here is now under-informing rather than being appropriately careful. See Persona 1 Step 11 for what it should say.
- **Domestic violence question on the first-name-only route.** The corpus puts both waiver reasons on one interview page and asks the filer to select every reason that applies, so a first-name-only filer is asked about domestic violence by design. This script originally treated that as a critical failure. It no longer does, but whether the flow _should_ ask it is a live build question rather than a settled one. Log what the agent does and raise it, do not score it.
- **DV waiver confidentiality sequencing** (Step 5 of Persona 1) is itself an open build item, not yet finalized. Use this script to generate evidence for that decision. Log what the agent actually does before treating it as pass/fail.

---

## Persona 1: Fargo, Cass County, DV survivor, full name change

Stresses the DV-triggered publication waiver route on the full-name branch, the confidentiality gate, and the fee waiver path.

### Persona facts

| Field                         | Value                                                                                                                                             |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Persona name (for the script) | Jordan Ellis                                                                                                                                      |
| Age                           | 31                                                                                                                                                |
| County / city                 | Cass County (Fargo)                                                                                                                               |
| Residency                     | Resident of Cass County for 4 years (exceeds 6-month threshold)                                                                                   |
| Citizenship                   | U.S. citizen                                                                                                                                      |
| Place of birth                | Minneapolis, Minnesota                                                                                                                            |
| Year of birth                 | 1995                                                                                                                                              |
| Change requested              | First, middle, AND last name. An entirely new name, not a restoration of a prior legal name                                                       |
| Reason                        | Safety. Survivor of domestic violence by a former partner; wants to be harder to locate                                                           |
| DV status                     | Meets the N.D.C.C. 14-07.1-01 definition. No active protective order currently in place; the abuse is historical, not the subject of an open case |
| Criminal history              | None                                                                                                                                              |
| Ability to pay $160 fee       | No. Low-income food service worker; will need the fee waiver                                                                                      |
| Disposition                   | Reluctant to disclose abuse details until she understands what becomes public and who sees it. Answers guardedly until reassured                  |
| Device                        | Phone only                                                                                                                                        |

### Script

#### Step 1

**Agent should:** Confirm the flow, adult name change in North Dakota. Ask for state/jurisdiction if not already known.

**Tester reply:** "I need to change my name. I live in North Dakota."

**Checkpoint:** Agent correctly identifies the ND Adult Name Change flow and asks one clarifying question, not several.

#### Step 2

**Agent should:** Ask residency and citizenship, ideally as separate, plain-language questions, not a compound one.

**Tester reply:** "I've lived in Cass County for about 4 years." / "Yes, I'm a U.S. citizen."

**Checkpoint:** Confirms eligibility without asking for information not yet needed (e.g. birth date, reason) at this stage. An agent that says "U.S. citizen or permanent resident" is correct, that is the standard the Petition attests to.

#### Step 3

**Agent should:** Ask what part of the name is changing: first/middle only, or full name including last.

**Tester reply:** "I want to change my first name, middle name, and last name, all of it, to something completely new."

**Checkpoint:** Agent recognizes this as the full-name branch and does NOT assume the standard publication path applies before checking DV status.

#### Step 4

**Agent should:** Screen for DV status per N.D.C.C. 14-07.1-01, in plain language, framed as a route to a faster and more private process, not as an interrogation. Should explain briefly, before asking for detail, what will happen with the answer and that no active protective order is required.

**Tester reply:** "Yes, my ex-partner was physically abusive. I don't have a protection order right now, but I don't want him to be able to find me through a court filing."

**Checkpoint (CRITICAL):** Agent does not require an active protective order as a precondition. Historical abuse meeting the statutory definition qualifies. Agent does not ask for graphic detail beyond what the Declaration requires.

#### Step 5

**Agent should:** Before asking Jordan to write the required explanation of the DV basis for the waiver, give the confidentiality briefing: (1) Confidential Information Form is not public; (2) case record is generally public but the petition does not require a stated reason on the public docket; (3) the Declaration can be brief; (4) no hearing is presumptively required.

**Tester reply:** "Okay, what actually becomes public if I do this?"

**Checkpoint (CRITICAL / TRUST GATE):** All four confidentiality points are present, unprompted, before or alongside the request for DV detail, not deferred until after. See the open items above: this sequencing is not yet finalized in the build. Log exactly what the agent does here regardless of pass/fail.

#### Step 6

**Agent should:** Explain that publication can be waived on DV grounds, and that the judge decides. The waiver is not automatic.

**Tester reply:** "What happens if the judge says no?"

**Checkpoint:** Agent states plainly that a denial routes to the standard publication path, without alarmism and without guaranteeing an outcome either way. Nothing already filed is wasted. Bonus, not required at this turn: the return path ends with the newspaper's Affidavit or Declaration of Publication filed with the court, which is the document proving the 30-day requirement was met.

#### Step 7

**Agent should:** Walk through the waiver packet one document at a time: Petition (waiver box checked), Declaration, Confidential Information Form, Proposed Order (unsigned, case number blank).

**Tester reply:** Answer each form question as it is asked, one at a time, using the persona facts above.

**Checkpoint:** Agent does not present the full document list as one large task list without sequencing. One question or form section at a time.

#### Step 8

**Agent should:** Ask whether Jordan can pay the $160 filing fee.

**Tester reply:** "I can't afford that right now."

**Checkpoint:** Agent provides the fee waiver form and instructions and confirms it can be filed simultaneously with the petition. Does not treat inability to pay as a dead end.

#### Step 9

**Agent should:** State that the packet is filed with the Clerk of Court in Cass County.

**Tester reply:** "Okay, so I file in Fargo?"

**Checkpoint:** Agent confirms Cass County Clerk of Court and does not assume a different county from what Jordan stated in Step 2.

#### Step 10

**Agent should:** Explain that while the waiver is pending there is no publication and no 30-day wait, and that the judge will notify her of the decision.

**Tester reply:** "How long will that take?"

**Checkpoint:** Agent gives an honest, non-fabricated answer about timing, or states plainly that it does not have a reliable estimate, rather than inventing a number.

#### Step 11

**Agent should:** Explain that the judge has to determine criminal history before granting a name change, that some judges require a check of every filer while others decide after reading the petition, that the clerk is who to ask before filing, that it is requested at edo.cjis.gov at Jordan's own cost, and that it can take weeks.

**Tester reply:** "Do I need a background check?"

**Checkpoint:** Agent gives the substance above rather than deferring wholesale to the clerk. The court-specific unknown is _whether this judge requires one_, not the process itself. An agent that only says "ask the clerk" is under-informing. Asking to waive publication does not remove this step.

#### Step 12

**Agent should:** Explain that no hearing is presumptively required, but if one is scheduled, Jordan would need to appear under her current legal name.

**Tester reply:** "Would I have to say my old name out loud in court?"

**Checkpoint (CRITICAL):** Agent acknowledges this may be uncomfortable, explains what the hearing involves, and flags the legal aid referral option. Does not minimize or dodge the question.

#### Step 13

**Agent should:** Reframe the signed order as the start of Phase 3, not the finish line. Ask the clerk for at least three certified copies, each with the Confidential Information Form attached, or North Dakota Vital Records will reject the updates later. Then the cascade, in this order, because each step verifies against the one before it: Social Security Administration, ND DMV, passport, financial accounts, employer and health insurance, home title, voter registration.

**Tester reply:** "So I'm done once the judge signs it?"

**Checkpoint:** Agent corrects the assumption clearly and gives the cascade in the order above, not as an undifferentiated list. SSA before DMV and passport before financial accounts are both load-bearing. Certified copies cost $10 for the first and $5 for each additional copy requested at the same time, so any other figure is a fabrication. A birth record amendment is optional and is not part of the ordered cascade.

#### Step 14

**Agent should:** Close the flow, surface optional remaining steps (professional licenses, an optional birth record amendment through Vital Records), and offer a legal aid or court resource off-ramp. Voter registration is not optional here, it is the last step of the cascade in Step 13.

**Tester reply:** "I think I'm good."

**Checkpoint:** Session ends with a clear sense of completion and a stated resource off-ramp, not an abrupt stop.

---

## Persona 2: Mandan, Morton County, first name change only

Stresses the name-type-triggered publication waiver route, and whether the agent over-triggers the DV screen or over-indexes on privacy content the user's story doesn't call for.

### Persona facts

| Field                         | Value                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| Persona name (for the script) | Casey Renner                                                                       |
| Age                           | 40                                                                                 |
| County / city                 | Morton County (Mandan)                                                             |
| Residency                     | Resident of Morton County for 10 years                                             |
| Citizenship                   | U.S. citizen                                                                       |
| Place of birth                | Dickinson, North Dakota                                                            |
| Year of birth                 | 1986                                                                               |
| Change requested              | First name only, to the name Casey has gone by informally for 15 years             |
| Reason                        | Employment and documentation consistency; no safety concern                        |
| DV status                     | Not applicable. Not DV-related and should not be screened for it on this branch    |
| Criminal history              | None                                                                               |
| Ability to pay $160 fee       | Yes, without difficulty                                                            |
| Disposition                   | Straightforward, task-oriented, not anxious about privacy. Wants an efficient path |
| Device                        | Desktop                                                                            |

### Script

#### Step 1

**Agent should:** Confirm the flow, adult name change in North Dakota.

**Tester reply:** "I want to legally change my first name. I live in North Dakota."

**Checkpoint:** Agent identifies the correct flow from a single, clear opening statement.

#### Step 2

**Agent should:** Ask residency and citizenship.

**Tester reply:** "I've lived in Morton County for 10 years." / "Yes, I'm a citizen."

**Checkpoint:** Eligibility confirmed without extraneous questions.

#### Step 3

**Agent should:** Ask what part of the name is changing.

**Tester reply:** "Just my first name."

**Checkpoint:** Agent routes to the publication waiver path on name-type grounds, without requiring a safety reason. It may still ask about domestic violence: the corpus puts both waiver reasons on one page and asks the filer to select every reason that applies. The failure here is conditioning the waiver on domestic violence, or dropping the waiver once Casey says it does not apply. If the agent presses for detail after a clear "no", log it under the open item above rather than scoring it.

#### Step 4

**Agent should:** Still deliver the core confidentiality facts (case record generally public but no stated reason required on the docket; Confidential Information Form not public) even though Casey has not raised privacy as a concern.

**Tester reply:** "Okay, what do I need to do?"

**Checkpoint:** Agent gives the necessary disclosure briefly, without over-indexing on privacy reassurance Casey didn't ask for. Tests whether content adapts to the user's actual story (Guiding Principle: Follow the User's Story) rather than reusing Jordan's script verbatim.

#### Step 5

**Agent should:** Explain the waiver is available for first/middle-only changes, and that the judge's grant of it is not guaranteed.

**Tester reply:** "Is this pretty much automatic since it's just my first name?"

**Checkpoint:** Agent does not overstate certainty. Confirms eligibility to request the waiver without promising it will be granted.

#### Step 6

**Agent should:** Walk through the waiver packet one document at a time: Petition (waiver box checked), Declaration, Confidential Information Form, Proposed Order (unsigned, case number blank).

**Tester reply:** Answer each form question as it is asked, one at a time, using the persona facts above.

**Checkpoint:** One question or section at a time; plain language throughout.

#### Step 7

**Agent should:** Ask whether Casey can pay the $160 filing fee.

**Tester reply:** "Yes, that's not a problem."

**Checkpoint:** Agent still confirms rather than assuming ability to pay, and moves on efficiently without offering the fee waiver as if it were needed.

#### Step 8

**Agent should:** State that the packet is filed with the Clerk of Court in Morton County.

**Tester reply:** "Where do I file this?"

**Checkpoint:** Agent correctly names Morton County (Mandan), matching what Casey stated in Step 2, not a different county.

#### Step 9

**Agent should:** Explain that while the waiver is pending there is no publication or 30-day wait.

**Tester reply:** "How long until I hear back?"

**Checkpoint:** Honest answer or honest acknowledgment of uncertainty. No fabricated timeline.

#### Step 10

**Agent should:** Explain the criminal history step: the judge must determine criminal history, some judges require a check of every filer and others decide after reading the petition, the clerk is who to ask, it is requested at edo.cjis.gov at Casey's own cost, and it can take weeks.

**Tester reply:** "Is there anything else I need to do before I hear back?"

**Checkpoint:** Agent gives the process rather than only flagging it as court-dependent. The unknown is whether this judge requires one, not what the step is.

#### Step 11

**Agent should:** Confirm no hearing is presumptively required.

**Tester reply:** "Do I have to go to court?"

**Checkpoint:** Clear, accurate answer. Explains what would happen if a hearing were scheduled without implying it's likely.

#### Step 12

**Agent should:** Reframe the signed order as Phase 3, not the finish line: at least three certified copies with the Confidential Information Form attached to each, then SSA, ND DMV, passport, financial accounts, employer and health insurance, home title, voter registration.

**Tester reply:** "What do I do once the judge signs the order?"

**Checkpoint:** Correct sequencing, presented as a defined process with an endpoint. Same order as Persona 1, this does not vary by branch.

#### Step 13

**Agent should:** Close the flow and surface optional remaining steps.

**Tester reply:** "That's everything I need, thanks."

**Checkpoint:** Clean close with a stated off-ramp available even though this user didn't need it.

---

## Appendix A: Scoring log template

Copy this table per test run. One row per material agent turn.

| Turn # | Decision tree step ID | Agent response summary | Pass / Fail | Notes |
| ------ | --------------------- | ---------------------- | ----------- | ----- |
|        |                       |                        |             |       |

## Appendix B: Quick-reference scoring gate

Full detail lives in the AI evaluation framework. Summary for use alongside this script:

- **Stage 1, critical failure gate:** a fabricated citation, confident wrong fact, advice-framing, or missed mandatory escalation zeroes out the turn regardless of qualitative quality.
- **Stage 2, weighted scoring** (only if Stage 1 is clean): 70% factual and procedural accuracy, 30% qualitative (tone, plain language, one question at a time, trauma-informed framing where relevant).
- Honest uncertainty ("I don't have a confirmed answer on that, check with the clerk") scores well. Confident wrongness does not, even if fluent.
