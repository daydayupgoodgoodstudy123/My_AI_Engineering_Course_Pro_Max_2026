# RiskMap — Pair Programming Interview

You are joining a team turning a roadmap into explicit assumptions and pre-registered experiments. The service ranks risk, keeps raw evidence and tells the team what to test or reconsider next. It uses the standard library and local deterministic observations.

**Time:** 60 minutes. Work through the five tests in order. Remove only the current test's skip marker. Keep every test and assertion unchanged.

## Pt 0 Setup

You need Python 3.10+ and pytest. Run `python -B -m pytest -q -p no:cacheprovider` in a temporary practice copy. Every part starts skipped. Unlock only the current part.

## Pt 1 `test_assumption_map`

Make `map_decision` agree with evidence and stable risk order; keep the large-map timing assertion passing.

## Pt 2 `test_csv_map_roundtrip`

Implement `MapStore` using two CSV tables. A reopened map must exactly match the original typed assumptions and experiments.

## Pt 3 `test_registered_experiment`

Implement the pre-registered, fixed-size evidence decision in `judge`, including explicit pass/fail/ambiguous actions.

## Pt 4 `test_online_experiment_decisions`

Implement `stream_experiments`. The test parser defines the logfmt wire format; the encoder and keyed accumulator are supplied.

## Pt 5 `test_composite_assumptions`

Implement the finite ALL/ANY assumption tree and choose the next experiment that can still affect its result.

Start with `python -B -m pytest -q`. The original suite has five skipped parts. Public docstrings define the contract; ask about unclear behavior. No model, network, external service or free-text inference is needed.
