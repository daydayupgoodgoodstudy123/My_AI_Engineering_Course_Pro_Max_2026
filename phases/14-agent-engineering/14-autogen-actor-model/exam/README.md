# ActorRT pair session

ActorRT is a small actor runtime for agents, modeled on AutoGen v0.4 Core. Actors keep private state and talk only through messages: `actorrt/runtime.py` queues and delivers them, fans topics out to their subscribers, and parks failed messages in a dead-letter queue, and `actorrt/review.py` holds the lesson's two-actor code review. `actorrt/journal.py` keeps the inbox on disk, `actorrt/teams.py` runs group chats on the runtime, and `actorrt/transport.py` carries messages to actors on another host.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_runtime_delivery`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the runtime fails.

## Pt 2 `test_journal_recovery`

Keep the inbox and the dead letters in a journal, so a crash loses nothing that was queued.

## Pt 3 `test_group_chat`

Run teams on the runtime: one that takes turns in a fixed rotation, and one where a selector picks who speaks next.

## Pt 4 `test_link_frames`

Talk to actors on another host over a byte stream.

## Pt 5 `test_spawn_tree`

Let actors spawn children, and stop whole subtrees.
