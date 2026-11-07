# PrimSwap pair session

PrimSwap replays scripted agents through shared-state primitives and three control modes. `primswap/state.py`, `agent.py` and `control.py` supply the primitives; `configuration.py` restores definitions and `replay.py` interprets who chooses the next agent.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest. Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_owned_primitives_and_latest_review`

Comment out `@pytest.mark.skip('Part 1')`, run pytest, and repair the agent policy boundary, canonical sender, target outcomes and latest-draft review service. Preserve exact sender names and incoming-message ownership as guards; the complete shared snapshot primitive is supplied.

## Pt 2 `test_durable_primitive_configuration`

Persist ordered immutable agent definitions and separately configured control, then bind reusable local policies.

## Pt 3 `test_three_control_origins`

Replay the same agents and initial state under static, handoff and external-selector control. Repeated static positions run separately; existing history does not spend a new invocation's step budget.

## Pt 4 `test_selected_control_json_sequence`

Project observed control decisions and typed stop records through the supplied record driver, retaining owned nested message payloads.

## Pt 5 `test_nested_primitive_ownership`

Bind nested component leaves to scoped identities, shared stores and inherited schedulers.
