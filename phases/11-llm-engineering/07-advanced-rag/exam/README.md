# RerankDesk pair session

RerankDesk prepares keyword and local hypothetical-document candidate batches for an injected pair scorer. `rerankdesk/search.py` owns candidate selection, while the lexical scorer, catalog store, query report and parent-context expansion are independent application features.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_filtered_candidate_batch`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why candidate preparation fails.

## Pt 2 `test_dbm_parent_child_catalog`

Save and restore the source, parent and child catalog, including raw source payload outside indexed intervals and sources without children.

## Pt 3 `test_source_lexical_pair_features`

Implement the local pair scorer and connect it to the candidate service. Keep source lowercase semantics for mixed-case input.

## Pt 4 `test_csv_query_batch_reports`

Project one completed query's original rank, rerank score and catalog provenance with report_rows. CSV encoding, header and the full async publication/ownership driver are supplied.

## Pt 5 `test_parent_context_match_tree`

Expand selected child evidence to its parent context, retaining each selected hit occurrence and its original evidence.
