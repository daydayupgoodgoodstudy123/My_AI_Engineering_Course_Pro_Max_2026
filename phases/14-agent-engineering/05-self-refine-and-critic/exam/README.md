# Critic pair session

Critic is a small evaluator-optimizer service. A model drafts a short bullet summary, a critic checks it, and the model refines it until the critic is satisfied: Self-Refine when the model critiques itself, CRITIC when an external verifier does (`critic/loop.py`). Every round can be kept on disk as a chain of line diffs (`critic/revisions.py`), each claim in a draft can be checked by a tool (`critic/evaluator.py`), drafts stream to clients through an output guardrail (`critic/guardrail.py`), and nested outlines get a critique that points at each bullet (`critic/outline.py`). The model and the tools are scripted stand-ins; nothing calls a real LLM or the network.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_refine_loop`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the refine loop misbehaves.

## Pt 2 `test_revision_chain`

Keep every round of the loop on disk, as a chain of line diffs.

## Pt 3 `test_claim_verification`

Check each claim with the tool for its kind, and decide when the loop should hand a draft to a person.

## Pt 4 `test_stream_guardrail`

Stream a draft to a client through an output guardrail.

## Pt 5 `test_outline_critique`

Critique a nested outline.
