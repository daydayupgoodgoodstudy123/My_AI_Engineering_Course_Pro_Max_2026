# SourceWeave pair session

SourceWeave is a small local retrieval service. `sourceweave/index.py` prepares context from a corpus generation. The store, evidence extractor, Markdown replay and recursive source chunker are separate application features.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_corpus_generation_and_context`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the context preparation service fails.

## Pt 2 `test_complete_snapshot_sqlite`

Save and reopen complete corpus snapshots, preserving their saved coordinate order and exact binary64 values.

## Pt 3 `test_extractive_answer_with_original_citation`

Answer from eligible retrieved evidence and retain its source. Source stopwords give no support; ten-character sentences are eligible.

## Pt 4 `test_markdown_evidence_replay`

Build the Markdown appendix for the sources actually cited in the completed answer. Original-fragment replay and source ownership are supplied.

## Pt 5 `test_boundary_first_recursive_chunks`

Chunk the supplied source boundaries within a word budget, preserving fitting paragraphs as well as sections.
