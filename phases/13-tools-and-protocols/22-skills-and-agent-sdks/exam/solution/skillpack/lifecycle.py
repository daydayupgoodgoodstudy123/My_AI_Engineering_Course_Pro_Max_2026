"""Check a host's lifecycle events, one skill session at a time, and report them as TAP."""
from __future__ import annotations

from collections.abc import AsyncIterator

# The lesson's eight stages, discovered first. Each later stage needs the one named here to
# have happened earlier in the same session.
NEEDS = {
    "validated": "discovered",
    "cataloged": "validated",
    "selected": "cataloged",
    "activated": "selected",
    "resource_loaded": "activated",
    "tool_called": "activated",
    "verified": "activated",
}
STAGES = ("discovered", *NEEDS)


async def tap_report(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Check every skill session against the lifecycle and stream one TAP line per session.

    An event is {"skill": name, "stage": stage, ...}, where stage is one of STAGES or
    "ended", which closes the skill's session. A session opens with the first event of a
    skill that has no open session, so a skill can have several sessions one after another,
    and the sessions of different skills interleave. A "validated" event carries "ok".

    A session fails on the first of these, which is its reason:
      - "<stage> after failed validation": any stage once validated came with ok False;
      - "<stage> before <needed>": a stage whose needed stage (NEEDS) has not happened yet;
      - "tool_called not verified": the session ends with a tool call that no verified
        event came after.

    The moment a session ends, emit "ok N - <skill>" or "not ok N - <skill> # <reason>",
    numbering sessions in the order they end. When the events run out, each session still
    open gets a line too, in the order the sessions opened, with its reason or "session not
    ended". The plan, "1..N", comes last. Every line ends with "\\n".
    """
    sessions: dict[str, _Session] = {}
    count = 0
    async for event in events:
        skill, stage = event["skill"], event["stage"]
        session = sessions.get(skill)
        if session is None:
            session = sessions[skill] = _Session()
        if stage == "ended":
            del sessions[skill]
            count += 1
            yield _line(count, skill, session.verdict())
        else:
            session.see(stage, event)
    for skill, session in sessions.items():
        count += 1
        yield _line(count, skill, session.reason or "session not ended")
    yield f"1..{count}\n"


class _Session:
    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.failed_validation = False
        self.unverified_call = False
        self.reason: str | None = None

    def see(self, stage: str, event: dict) -> None:
        if self.reason is None:
            if self.failed_validation:
                self.reason = f"{stage} after failed validation"
            elif stage in NEEDS and NEEDS[stage] not in self.seen:
                self.reason = f"{stage} before {NEEDS[stage]}"
        self.seen.add(stage)
        if stage == "validated" and not event.get("ok"):
            self.failed_validation = True
        elif stage == "tool_called":
            self.unverified_call = True
        elif stage == "verified":
            self.unverified_call = False

    def verdict(self) -> str | None:
        if self.reason is None and self.unverified_call:
            return "tool_called not verified"
        return self.reason


def _line(number: int, skill: str, reason: str | None) -> str:
    if reason is None:
        return f"ok {number} - {skill}\n"
    return f"not ok {number} - {skill} # {reason}\n"
