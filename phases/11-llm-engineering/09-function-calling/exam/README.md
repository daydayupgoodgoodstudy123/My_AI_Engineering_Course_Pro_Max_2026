# LocalToolBench

A local tool service with a typed table query exercise. Python 3.10+, standard library and pytest only.

Keep the tests as written. Ask questions, explain your reasoning, and look up documentation when useful. Unlock one part at a time.

## Pt 1 `test_local_dispatch_and_bound_scan`

Make registered tools and bound table requests satisfy their contracts.

## Pt 2 `test_invocation_audit_journal`

Persist and replay the complete invocation history, including separate calls with matching arguments.

## Pt 3 `test_allowlisted_typed_query_compiler`

Compile and execute the restricted typed table query against each allowed table’s own schema.

## Pt 4 `test_completed_tool_probe_tap`

Report completed local tool probes with their original labels and structured outcomes.

## Pt 5 `test_recursive_syntax_audit`

Inspect the submitted code's syntax tree in field order without executing it.
