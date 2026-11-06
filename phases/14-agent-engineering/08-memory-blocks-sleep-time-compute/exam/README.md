# MemBlocks pair session

MemBlocks is a small agent-memory service in the style of Letta. Core memory is a set of labeled, size-capped blocks the model edits with `block_append` and `block_replace` (`memblocks/blocks.py`). Older facts live in an archival tier that invalidates records but never deletes them (`memblocks/archival.py`). A sleep-time agent tidies both between turns, off the critical path (`memblocks/agents.py`), so the primary agent never waits on memory work.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_block_tools`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the block code fails.

## Pt 2 `test_version_log`

Keep every version of every block on disk.

## Pt 3 `test_sleep_consolidation`

Let the sleep-time agent find stale and duplicate archival records on its own.

## Pt 4 `test_sleep_alongside_turns`

Run the sleep-time agent while the primary agent keeps serving turns.

## Pt 5 `test_lineage_invalidation`

When a record goes stale, take down everything that was consolidated from it.
