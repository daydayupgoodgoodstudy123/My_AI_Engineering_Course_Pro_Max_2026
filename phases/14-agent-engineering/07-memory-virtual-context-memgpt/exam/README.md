# memgpt pair session

memgpt is a small MemGPT-style memory layer for an agent. The main context (`memgpt/context.py`) is the part of the prompt the model always sees: pinned core sections, a running summary and the most recent messages, kept under a token budget. Archival memory (`memgpt/archival.py`) is the external, searchable store of facts, each cited to the session and turn it came from. `memgpt/tools.py` exposes the five memory tools the model calls.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_tools_and_budget`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the memory tools fail.

## Pt 2 `test_archive_roundtrip`

Keep archival memory in SQLite, so that it survives a restart.

## Pt 3 `test_bm25_recall`

Rank archival facts with BM25, and measure its recall against token overlap.

## Pt 4 `test_pager_stream`

Page the main context out as messages stream in.

## Pt 5 `test_typed_core`

Give core memory typed, nested sections.
