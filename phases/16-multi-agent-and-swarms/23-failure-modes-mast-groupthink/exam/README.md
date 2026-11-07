# MASTStorm — Circuit Recovery and Causal Retry Amplification

Original offline interview practice for Phase 16 / Lesson 23. Suggested duration: 60 minutes; this budget has not been calibrated with human candidates. Python 3.10+, standard library and pytest.

Maintain a deterministic incident and retry service. Work through the five parts in order, preserving the stated contracts and using the complete supplied dependencies.

## Pt 1 — Detection and breaker recovery

Repair incident detection and the breaker lifecycle, then replay the complete outcome stream efficiently. Preserve original evidence, all admission decisions and the actual final window.

## Pt 2 — Incident CSV archive

Persist and reopen complete incident snapshots with their independent observations. Keep every appended row, its original associations and its declared order, including the explicit primary symptom.

## Pt 3 — Causal retries

Implement shared actual-call admission, bounded dependency retries and the complete cascade report, honoring each configured attempt bound and visiting every dependency. Reuse successful effects and distinguish provider outcomes from non-invocations.

## Pt 4 — Incident syslog feed

Project each actual incident phase and its own observation into the supplied syslog adapter. Keep event correlation and close only on the declared positive validation evidence.

## Pt 5 — Nested amplification audit

Explain the complete supplied retry trace with recursive edge and invocation accounting. Retain actual occurrences, complete ancestor retry paths, first actual service order and the originating request correlation.

## Working rules

Edit the candidate modules in `maststorm/`; keep support implementations and test assertions intact. Unlock only the active Part by removing its skip decorator, then retain earlier unlocked tests.

Read [使用说明.md](使用说明.md) for backup, commands and reset. Keep `solution/` and `INTERVIEWER.md` closed during an independent attempt; use [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md) afterward.

The complete local rolling-window workload and timing boundary are recorded in SCOPE.json; preserve the whole-output contract when repairing the implementation.
