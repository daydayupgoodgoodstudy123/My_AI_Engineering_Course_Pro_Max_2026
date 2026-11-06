# BitVecBank pair session

BitVecBank is a small embedding inspection service. Projection and metric code lives in `bitvecbank/metrics.py`, a binary vector bank lives in `bitvecbank/store.py`, and `bitvecbank/search.py` handles compressed candidate search. `bitvecbank/service.py` prepares vector inspection cards for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_vector_inspection_pipeline`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why vector inspection fails. Stable numeric direction helpers are supplied.

## Pt 2 `test_binary64_bank_roundtrip`

Build the vector bank in the declared little-endian binary64 format.

## Pt 3 `test_binary_first_dense_rerank`

Search the compressed candidates and refine the results.

## Pt 4 `test_packed_vector_wire_stream`

Encode the BVS1 header and complete raw vector records under the declared dimension. The asynchronous publication and source ownership driver is supplied.

## Pt 5 `test_supplied_layer_descent`

Inspect the supplied directed multilayer neighbor graph.
