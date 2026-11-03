# ToolLint pair session

ToolLint is the tool-schema linter a team runs over its tool registry in CI. Findings come from the naming, description and schema rules (`toollint/rules.py`), every release of the registry is stored content-addressed (`toollint/releases.py`), two releases are compared under the versioning rules (`toollint/compat.py`), a registry that arrives page by page is linted as it streams in (`toollint/stream.py`), and the "use <tool> instead" pointers in descriptions form a graph (`toollint/refs.py`). `toollint/service.py` wires the release gate together for the CI job.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_lint_registry`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the linter fails.

## Pt 2 `test_release_store`

Store every release of the registry.

## Pt 3 `test_breaking_changes`

Tell a safe release from a breaking one.

## Pt 4 `test_lint_stream`

Lint a registry that arrives a page at a time.

## Pt 5 `test_reference_graph`

Check where the descriptions send the model.
