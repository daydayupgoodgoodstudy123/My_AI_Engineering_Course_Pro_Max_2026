# SkillRoute pair session

SkillRoute is the invocation layer of a skill host. It decides who may start which discovered skill and routes requests to them (`skillroute/policy.py`, `skillroute/router.py`), keeps a skill run's progress in a JSON file the run can resume from (`skillroute/state.py`), turns invocation text into the typed arguments a tool takes (`skillroute/arguments.py`), follows skills through a multi-turn session as an NDJSON event stream (`skillroute/session.py`), and serves skill-to-skill calls (`skillroute/compose.py`). `skillroute/service.py` is the front door for explicit invocations.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_route_eligible_first`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the router picks the wrong skills.

## Pt 2 `test_resume_state`

Let a skill run pick up where it stopped.

## Pt 3 `test_bind_arguments`

Turn an invocation's text into the arguments a tool call takes.

## Pt 4 `test_session_lifecycle`

Follow skills through a conversation, turn by turn.

## Pt 5 `test_skill_chains`

Let skills call other skills.
