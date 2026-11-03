# agentcard pair session

agentcard is a small A2A harness. The writer agent from the lesson serves `tasks/send` and follow-up messages for the skills on its Agent Card (`agentcard/writer.py`), and the calling agent downloads the report it returns (`agentcard/caller.py`). `agentcard/store.py` keeps tasks in SQLite, `agentcard/cards.py` checks, signs and discovers Agent Cards and picks the skill a message goes to, `agentcard/frames.py` streams a task over a length-prefixed binding, and `agentcard/delegation.py` works out what each caller sees of a multi-hop delegation. Tasks, messages, parts and artifacts are defined in `agentcard/model.py`.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_writer_lifecycle`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the writer code fails.

## Pt 2 `test_task_store_roundtrip`

Keep the writer's tasks in SQLite, so they survive a restart.

## Pt 3 `test_discover_and_choose`

Discover an agent from its signed Agent Card, and pick the skill a message goes to.

## Pt 4 `test_stream_frames`

Stream a task over the length-prefixed binding, and read the stream back.

## Pt 5 `test_delegation_views`

Work out what each caller sees of a multi-hop delegation.
