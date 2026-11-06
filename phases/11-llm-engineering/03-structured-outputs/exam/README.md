# FieldShape pair session

FieldShape is a small structured-extraction service. Model fields become schemas in `fieldshape/flat.py` and `fieldshape/compiler.py`, descriptor snapshots live in `fieldshape/store.py`, and completed extraction strings are replayed in `fieldshape/replay.py`. `fieldshape/service.py` wires compilation to the existing validator.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_flat_extraction_adapter`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why flat extraction validation fails.

## Pt 2 `test_descriptor_snapshot`

Build the descriptor store, preserving metadata exactly across replacements.

## Pt 3 `test_recursive_model_compiler`

Compile the composed model descriptors with constraints on their own nodes.

## Pt 4 `test_completed_extraction_replay`

Classify the completed extraction strings as they arrive, preserving their evidence.

## Pt 5 `test_typed_issue_tree`

Organize every validator issue into a report tree with literal typed keys.
