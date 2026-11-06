# contractkit pair session

contractkit is the host side of MCP tool contracts, for the stateless 2026-07-28 protocol. `contractkit/client.py` pages through a server's `tools/list`, admits the descriptors that pass `contractkit/contract.py`, and checks each call's arguments and result against what the tool published (`contractkit/schema.py` is the small JSON Schema subset it enforces). `contractkit/archive.py` stores the content blocks of results in a binary container. `contractkit/headers.py` mirrors annotated arguments into `Mcp-Param-*` headers and checks them at the HTTP boundary, `contractkit/completion.py` drives `completion/complete` while the user types, and `contractkit/annotations.py` audits where a descriptor puts its `x-mcp-header` annotations.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_discover_and_call`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the client fails.

## Pt 2 `test_content_container_roundtrip`

Archive content blocks with the supplied binary framing and enforce the caller's local media and embedded-resource payload limits.

## Pt 3 `test_parameter_headers`

Mirror present arguments into headers and check the mirror in bindings order. Primitive argument rendering is provided.

## Pt 4 `test_completion_debounce`

Ask for completions while the user types.

## Pt 5 `test_annotation_audit`

Audit where a descriptor puts its header annotations.
