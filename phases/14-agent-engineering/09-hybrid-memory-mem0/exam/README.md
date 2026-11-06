# HybridMem pair session

HybridMem is a small Mem0-shaped memory service for agents. `hybridmem/memory.py` writes every memory to three stores at once: a vector store for similarity search (token overlap stands in for an embedding model), a KV store keyed on `(user_id, fact_type, entity)`, and a graph store of typed edges that remember when they held (`hybridmem/graph.py`). Memories are scoped to a user, a session or an agent, and `hybridmem/context.py` turns search results into the memories section of a prompt. The extractor and the embedding model are stand-ins, so everything runs offline.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_scoped_search`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why search and the graph store fail.

## Pt 2 `test_sqlite_roundtrip`

Save the three stores to SQLite, and load them back.

## Pt 3 `test_fused_recall`

Fuse what the three stores find into one ranked list.

## Pt 4 `test_write_audit`

Run the write path over a live stream of messages and lookups, and audit every decision.

## Pt 5 `test_graph_as_of`

Answer questions about the past from the graph.
