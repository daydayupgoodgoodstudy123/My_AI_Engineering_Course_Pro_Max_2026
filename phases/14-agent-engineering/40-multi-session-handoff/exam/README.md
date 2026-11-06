# HandoffPkt pair session

HandoffPkt writes the packet a coding agent leaves behind when its session ends. `handoffpkt/packet.py` builds the seven fields (summary, changed files, commands run, failed attempts, open risks, next action, verdict pointer) from the workbench artifacts and renders them twice: `handoff.json` for the next agent and `handoff.md` for the human. Around it sit a history of every session's packet (`handoffpkt/history.py`), the cleanup checks that must pass before a packet is written (`handoffpkt/cleanup.py`), a one-pass trimmer for feedback logs too long to load (`handoffpkt/stream.py`), and a walk over the packets of a task that forked into branches (`handoffpkt/chain.py`). Nothing calls a model or the network; the tests hand in the artifacts.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_generate_handoff`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the generator fails.

## Pt 2 `test_history_roundtrip`

Keep every session's packet, so the next session can find the latest one and walk back from it.

## Pt 3 `test_clean_state`

Check that the workbench is clean before a packet gets written.

## Pt 4 `test_trim_stream`

Trim a feedback log that is far too long to load.

## Pt 5 `test_branch_heads`

The task forked into branches. Work out where each branch's next session starts.
