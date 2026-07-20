# Review instructions

## Skip branch-sync PRs

Do not review pull requests that merge one long-lived branch into another
(for example main into staging, or staging into main). Post no findings and
no summary comment. The commits in these PRs were already reviewed on their
feature PRs; anything flagged there was fixed or intentionally dismissed at
merge time, and re-raising it on the sync PR re-litigates settled decisions.

Review feature branches into main as normal.
