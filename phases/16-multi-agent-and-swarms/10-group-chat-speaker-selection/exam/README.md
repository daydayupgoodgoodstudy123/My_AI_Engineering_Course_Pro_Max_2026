# FloorFair conversation desk

FloorFair records local selector decisions, committed utterances and named-question obligations. Complete the five parts in order, editing only `floorfair/` so that the tests pass as written.

## Pt 0 Setup

Use Python 3.10+ and pytest. Run `python3 -m pytest` from your practice copy; all five parts start skipped. The 60-minute budget has not been calibrated with human candidates.

## Pt 1 `test_review_chat_replay`

Remove the Part 1 skip and repair the review-chat replay. Preserve real approval, complete recent selector input and actual speech counts while keeping the full conversation responsive.

## Pt 2 `test_selector_audit_archive`

Persist and reopen complete conversation snapshots in their declared roster and observation order. Retain each decision's own input, choice and reason, and every utterance's association with its decision.

## Pt 3 `test_named_question_deficit_policy`

Maintain named unanswered questions, compute weighted actual-turn deficits and select the next eligible speaker. Respect the consecutive cap and declared tie order.

## Pt 4 `test_public_selector_logfmt`

Project each classified observation's own public evidence into logfmt fields. Classification, binding, exact delta formatting and async transport are supplied.

## Pt 5 `test_nested_reply_authority_and_budget`

Audit each thread's complete cumulative per-agent speaking quotas, first excess evidence, own unanswered questions and inherited total speech budgets. Reply authority, global question identity and subtree lookups are supplied.
