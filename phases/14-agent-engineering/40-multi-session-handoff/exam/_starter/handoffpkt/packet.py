"""The handoff packet: the seven fields, generated from the workbench artifacts.

handoff.json (packet_json) is what the next agent loads; handoff.md (render_markdown) is what
the human reads. Both come from one HandoffPayload, and if they ever disagree the JSON wins.
"""
from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field

TAIL_K = 5
MAX_PACKET_BYTES = 64 * 1024
REVIEW_FLOOR = 7


class NoNextAction(ValueError):
    """The state has no next_action. Without one the packet is a status report, not a handoff."""


class PacketTooLarge(ValueError):
    """The packet does not fit max_bytes even with every commands_run entry left out."""


class DirtyWorkbench(RuntimeError):
    """clean_state still lists blocking issues, so no packet is written."""

    def __init__(self, issues: list[str]) -> None:
        super().__init__(f"{len(issues)} blocking issue(s): {issues}")
        self.issues = issues


@dataclass
class WorkbenchSnapshot:
    """Everything the generator reads at session end.

    state is agent_state.json, verdict is verification_report.json and review is
    review_report.json, or None when no review report was written. feedback is
    feedback_record.jsonl in log order, one dict per record as lesson 37 writes them
    (command is an argv list, exit_code is an int or None). diff_summary is {"touched": [path, ...]}.
    """

    task_id: str
    state: dict
    verdict: dict
    review: dict | None
    feedback: list[dict]
    diff_summary: dict


@dataclass
class HandoffPayload:
    task_id: str
    branch: str | None
    last_known_good_commit: str | None
    summary: str
    changed_files: list[str]
    commands_run: list[str]
    commands_omitted: int
    failed_attempts: list[str]
    open_risks: list[dict]
    next_action: str
    verdict_pointer: dict
    feedback_tail: list[dict] = field(default_factory=list)


def shell_line(command) -> str:
    """A command as one shell line: an argv list goes through shlex.join, a string stays as it is."""
    if isinstance(command, str):
        return command
    return shlex.join(str(part) for part in command)


def failed(record: dict) -> bool:
    """A record failed unless its exit_code is 0.

    exit_code None means the command never finished (a timeout, a missing binary). That is a
    failure too: the next session has to know the command gave no answer.
    """
    return record.get("exit_code") not in (0, None)


def describe_failure(record: dict) -> str:
    """One failed_attempts entry: 'pytest -x -> exit 1', or '... -> no exit code (timeout after 30.0s)'."""
    code = record.get("exit_code")
    outcome = "no exit code" if code is None else f"exit {code}"
    text = f"{shell_line(record.get('command', ''))} -> {outcome}"
    if record.get("error"):
        text += f" ({record['error']})"
    return text


def trim_feedback(records: list[dict], k: int = TAIL_K) -> list[dict]:
    """The last k records plus every earlier record that failed, in log order.

    Each record is kept as it is and appears once, also when two records are equal (two runs
    of the same command are two records). The input list is not changed.
    """
    tail = records[-k:]
    kept: list[dict] = []
    seen: set[int] = set()
    for record in tail + [r for r in records if failed(r)]:
        if id(record) not in seen:
            seen.add(id(record))
            kept.append(record)
    return kept


def review_total(review: dict) -> int:
    """The review's total score out of 10 (lesson 39)."""
    raw = review.get("total", 10)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 10


def derive_risks(snapshot: WorkbenchSnapshot) -> list[dict]:
    """open_risks, in this order:

    - every gate finding whose severity is "block" or "warn", as {"severity", "detail"};
    - one warn risk per open blocker in the state: "open blocker: <blocker>";
    - the review. A missing review report is itself a warn risk ("review report missing"), and
      so is a total that is not an integer ("review total 'n/a' is not a number"). A total below
      7 is a warn risk ("review total 5 below 7"). A review nobody wrote is never read as a pass.
    """
    risks: list[dict] = []
    for finding in snapshot.verdict.get("findings") or []:
        if isinstance(finding, dict) and finding.get("severity") in ("block", "warn"):
            risks.append({"severity": finding["severity"], "detail": str(finding.get("detail"))})
    for blocker in snapshot.state.get("blockers") or []:
        risks.append({"severity": "warn", "detail": f"open blocker: {blocker}"})
    total = review_total(snapshot.review)
    if total < REVIEW_FLOOR:
        risks.append({"severity": "warn", "detail": f"review total {total} below {REVIEW_FLOOR}"})
    return risks


def summarize(snapshot: WorkbenchSnapshot, failures: int) -> str:
    """One line on what the session did, built from the artifacts, never written by hand."""
    gate = {True: "passed", False: "failed"}.get(snapshot.verdict.get("passed"), "missing")
    if snapshot.review is None:
        review = "missing"
    else:
        review = f"{snapshot.review.get('verdict')} ({snapshot.review.get('total')}/10)"
    files = len(set(snapshot.diff_summary.get("touched") or []))
    return (
        f"{snapshot.task_id}: {len(snapshot.feedback)} commands run, {failures} failed; "
        f"{files} files changed; gate {gate}; review {review}."
    )


def packet_json(payload: HandoffPayload) -> str:
    """handoff.json: the payload as indented JSON. The same payload always gives the same text."""
    return json.dumps(asdict(payload), indent=2, ensure_ascii=False) + "\n"


def packet_size(payload: HandoffPayload) -> int:
    """The size of handoff.json in bytes (UTF-8)."""
    return len(packet_json(payload).encode("utf-8"))


def fit_budget(payload: HandoffPayload, max_bytes: int) -> HandoffPayload:
    """Make handoff.json fit in max_bytes by leaving out the oldest commands_run entries.

    The packet keeps as many of the most recent commands as fit, in order, and commands_omitted
    counts the ones left out; the full feedback log still has them. Nothing else is dropped to
    make room: a packet that does not fit even with no commands raises PacketTooLarge.
    """
    while packet_size(payload) > max_bytes:
        if not payload.commands_run:
            raise PacketTooLarge(f"{payload.task_id}: the packet needs more than {max_bytes} bytes without any commands")
        payload.commands_run.pop(0)
        payload.commands_omitted += 1
    return payload


def build_payload(snapshot: WorkbenchSnapshot, max_bytes: int = MAX_PACKET_BYTES) -> HandoffPayload:
    """The packet's fields, from the artifacts alone.

    next_action is the state's next_action on one line (runs of whitespace become one space).
    A missing or blank next_action raises NoNextAction. changed_files is every touched path once,
    sorted, so that the same artifacts always give the same packet. commands_run is every
    command's shell line, oldest first, until fit_budget trims it. failed_attempts describes every
    record that failed, in log order. feedback_tail is trim_feedback(feedback).
    """
    state = snapshot.state
    next_action = " ".join(str(state.get("next_action") or "").split())
    if not next_action:
        raise NoNextAction(f"{snapshot.task_id}: no next_action in the state; that is a status report")
    failures = [record for record in snapshot.feedback if failed(record)]
    payload = HandoffPayload(
        task_id=snapshot.task_id,
        branch=state.get("branch"),
        last_known_good_commit=state.get("last_known_good_commit"),
        summary=summarize(snapshot, len(failures)),
        changed_files=sorted(set(snapshot.diff_summary.get("touched") or [])),
        commands_run=[shell_line(record.get("command", "")) for record in snapshot.feedback],
        commands_omitted=0,
        failed_attempts=[describe_failure(record) for record in failures],
        open_risks=derive_risks(snapshot),
        next_action=next_action,
        verdict_pointer={
            "verdict": f"outputs/verification/{snapshot.task_id}.json",
            "review": f"outputs/review/{snapshot.task_id}.json",
        },
        feedback_tail=trim_feedback(snapshot.feedback),
    )
    return fit_budget(payload, max_bytes)


def render_markdown(payload: HandoffPayload, state: dict) -> str:
    """handoff.md, rendered from the payload and nothing else."""

    def bullets(items: list[str]) -> list[str]:
        return items or ["- none"]

    commands = [f"- `{command}`" for command in payload.commands_run]
    if payload.commands_omitted:
        commands.append(f"- ... and {payload.commands_omitted} earlier commands, in the full feedback log")
    lines = [
        f"# Handoff: {payload.task_id}",
        "",
        f"**Summary.** {payload.summary}",
        "",
        f"**Branch.** `{payload.branch}` at `{payload.last_known_good_commit}`",
        "",
        "## Changed files",
        *bullets([f"- `{path}`" for path in payload.changed_files]),
        "",
        "## Commands run",
        *bullets(commands),
        "",
        "## Failed attempts",
        *bullets([f"- {attempt}" for attempt in payload.failed_attempts]),
        "",
        "## Open risks",
        *bullets([f"- [{risk['severity']}] {risk['detail']}" for risk in payload.open_risks]),
        "",
        "## Next action",
        str(state.get("next_action", payload.next_action)),
        "",
        "## Receipts",
        f"- verdict: `{payload.verdict_pointer['verdict']}`",
        f"- review: `{payload.verdict_pointer['review']}`",
    ]
    return "\n".join(lines) + "\n"


def generate_handoff(
    snapshot: WorkbenchSnapshot,
    *,
    clean_state: list[str] = (),
    max_bytes: int = MAX_PACKET_BYTES,
) -> tuple[str, HandoffPayload]:
    """(handoff.md text, payload) for one session.

    clean_state is the cleanup phase's list of blocking issues. An empty list is the
    precondition: while it lists anything, raise DirtyWorkbench and build nothing.
    """
    if clean_state:
        raise DirtyWorkbench(list(clean_state))
    payload = build_payload(snapshot, max_bytes)
    return render_markdown(payload, snapshot.state), payload
