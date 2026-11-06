"""Leave a clean state: the checks that run before a handoff packet is generated."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoSnapshot:
    """What the cleanup phase sees of the repository at session end.

    status    `git status --porcelain` lines: " M app/signup.py", "?? notes.tmp", "R  old.py -> new.py"
    stashes   `git stash list` lines. `git stash push -m <note>` gives
              "stash@{1}: On feat/x: <note>"; a stash made without a note reads
              "stash@{0}: WIP on feat/x: 4be1c0d <last commit subject>"
    files     every file in the working tree, tracked or not, as repo-relative paths
    diff      the unified diff of this session's work, `git diff <session start>..HEAD`
    tests     {pytest node id: "passed" | "failed" | "error" | "skipped"} from the last run
    open_risks  the risks the packet will carry; a risk about a red test names it in "test"
    board     feature_list.json: {"active": id or "", "features": [{"id", "status"}, ...]}
    finished  ids of the features whose done_when passed this session
    branch    the checked-out branch, None when HEAD is detached
    branches  {local branch: whether it is merged into base_branch}
    """

    status: list[str] = field(default_factory=list)
    stashes: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    diff: str = ""
    tests: dict[str, str] = field(default_factory=dict)
    open_risks: list[dict] = field(default_factory=list)
    board: dict = field(default_factory=dict)
    finished: list[str] = field(default_factory=list)
    branch: str | None = "main"
    expected_branch: str = "main"
    base_branch: str = "main"
    branches: dict[str, bool] = field(default_factory=dict)


def clean_state(repo: RepoSnapshot) -> list[str]:
    """The blocking issues, the contents of clean_state.json. An empty list means clean.

    The five checks run in this order. Within a check the rows come in the order below, and each
    row reports in the order of its input. "scratch dir" and "temp file" both read files, so they
    come interleaved, in the order of files:

    working tree     "uncommitted: <path>"        every status line; a rename reports its new path
                     "stash without a note: <ref>"   a stash made without -m: its message, after
                                                  "stash@{n}: ", starts with "WIP on <branch>:"
    temp artifacts   "scratch dir: <dir>/"        a path segment named scratch, other than the file
                                                  name; <dir> is the path up to and including it,
                                                  reported once, at its first file; files inside it
                                                  report nothing else
                     "temp file: <path>"          any other file whose name, the last path segment,
                                                  ends with .tmp
                     "debug print: <path>:<line>" a line this session added to a .py file that, with
                                                  its indentation stripped, starts with print(,
                                                  pprint( or breakpoint(; <line> is its line number
                                                  in the new file
    tests            "red test: <node id>"        failed or error, and no open risk has that whole
                                                  node id as its "test"
    feature board    "features in_progress at once: <id>, <id>"   more than one in_progress, in board order
                     "finished feature not marked done: <id>"
                     "active feature is done: <id>"
    branch           "detached HEAD", or "wrong branch: <branch> (expected <expected_branch>)"
                     "orphan branch: <name>"      not merged, and neither base_branch nor expected_branch
    """
    raise NotImplementedError
