# SOPForge role-specialization desk

SOPForge connects structured specifications, local trusted-code artifacts and separate critic/verifier evidence. Complete the five parts in order, editing only `sopforge/` so that the tests pass as written.

## Pt 0 Setup

Use Python 3.10+ and pytest. Run `python3 -m pytest` from your practice copy; the five parts start skipped. The 60-minute budget has not been calibrated with human candidates.

## Pt 1 `test_complete_trusted_verification`

Remove the Part 1 skip and repair the critic/verifier path. Compile and bind the trusted artifact once per verification, retaining every declared case and using the supplied fresh execution session.

## Pt 2 `test_revision_bound_role_store`

Persist and reopen a complete SQLite snapshot. Keep all planner specifications, including those awaiting artifacts, and link each artifact revision to its distinct role reports; the codec and transaction primitives are supplied.

## Pt 3 `test_role_owned_clarification_resume`

Ask the declared owner for missing required information, accept only a matching active answer and resume the blocked step. Preserve unrelated work, reject another target while one is blocked, and use the repaired critic/verifier after execution.

## Pt 4 `test_completed_verifier_junit`

Project every completed verifier case into its own JUnit evidence, keeping specification revision identity and each case's own arguments. The outcome classifier, XML writer and async publication driver are supplied.

## Pt 5 `test_nested_role_artifact_contracts`

Audit typed producer/consumer ports and declared outputs at every nested SOP stage, requiring the declared input producer and keeping unexposed outputs local. Complete identity resolution and revision-link validation are supplied.
