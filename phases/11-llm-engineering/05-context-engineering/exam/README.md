# ContextLoom pair session

ContextLoom is a small context assembly service. Selected documents flow through `contextloom/filtering.py`, slot budgets live in `contextloom/budget.py`, and `contextloom/history.py` maintains the conversation context. `contextloom/service.py` wires the pieces together for preview and layout requests.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_context_preview_and_budget`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the context preview and budget pipeline fails.

## Pt 2 `test_component_revision_replay`

Build the component revision store with strictly advancing appends.

## Pt 3 `test_retrieved_block_zigzag`

Place every selected retrieved component.

## Pt 4 `test_context_revision_sse`

Encode each applied context update as a complete SSE snapshot. The supplied async driver publishes events and closes the update source.

## Pt 5 `test_bottom_up_document_digest`

Digest the supplied document hierarchy with ordered sources.
