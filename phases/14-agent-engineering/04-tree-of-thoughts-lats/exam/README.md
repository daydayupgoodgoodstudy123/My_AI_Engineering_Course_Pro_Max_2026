# ThoughTree pair session

ThoughTree searches the Game of 24 the way Tree of Thoughts and LATS search a reasoning problem. A state is the numbers still to combine, and a step combines two of them (`thoughtree/game.py`, which also holds the judge that scores states). `thoughtree/tot.py` runs a ToT beam search; `thoughtree/mcts.py` runs a LATS-style Monte Carlo Tree Search over the tree in `thoughtree/tree.py`; long searches are saved by `thoughtree/checkpoint.py`; `thoughtree/stream.py` runs ToT against a slow, metered LLM judge; and `thoughtree/expr.py` turns a solution back into an expression. `thoughtree/service.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_tot_search`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the search fails.

## Pt 2 `test_checkpoint_roundtrip`

Checkpoint a long search, and load it back.

## Pt 3 `test_mcts_search`

Search the deal with MCTS.

## Pt 4 `test_stream_judging`

Judge states with an LLM on a token budget, and stream each judgement as it comes back.

## Pt 5 `test_expression_tree`

Turn a solution back into one expression.
