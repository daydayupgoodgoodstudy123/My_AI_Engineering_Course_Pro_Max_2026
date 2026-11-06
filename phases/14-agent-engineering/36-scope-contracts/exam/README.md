# TaskScope pair session

TaskScope checks an agent's work against its scope contract. A contract (`taskscope/contract.py`) says which files a task may write and must never touch, which acceptance commands prove it done, and how much time, network egress and scope slip it gets; a project contract and a task contract merge by least privilege. `taskscope/check.py` compares a run (touched files, commands, minutes, hosts) with the contract and hands tagged findings to the verification gate. Around it sit the contract glob lists (`taskscope/patterns.py`, `taskscope/globs.py`), an archive of closed reports (`taskscope/archive.py`), a scanner that reads `git diff` as it streams (`taskscope/diffscan.py`) and the chain of contracts from the project down to a subtask (`taskscope/layers.py`).

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.11+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_scope_check`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the checker fails.

## Pt 2 `test_archive_roundtrip`

Archive closed reports, one file per task, so that nobody can rewrite the evidence later.

## Pt 3 `test_glob_dialect`

Contract globs are matched with `fnmatch`, which reads `**` and `*` differently from the people who write contracts. Implement the glob dialect and path normalization in `taskscope/globs.py`, and switch the checker over to them.

## Pt 4 `test_diff_scan`

Check a `git diff` while it streams in, and report each violation as soon as its file header has been read.

## Pt 5 `test_contract_chain`

Resolve the contracts from the project down to a subtask, and explain which one rules a path or a host out.
