"""Enforce the rule set while a turn runs, and report it as TAP."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .checker import THRESHOLD
from .rules import Rule
from .timeline import Watch
from .turn import Event


class Runtime:
    """The runtime side of the rule set: it catches violations during a turn.

    Runtime(rules) resolves every rule's check on watch first (BrokenRule as judge() says).
    run() reads the turn's events as they arrive and yields one TAP line per rule, the moment
    the rule's verdict is known, and then the plan:

        not ok N - <slug> # event <i> refused   a block rule broken by event i, which was refused
        not ok N - <slug> # event <i>           a warn or info rule broken by event i, which went through
        not ok N - <slug> # end of turn         a definition_of_done rule with no proof
        ok N - <slug>
        1..<number of rules>

    N counts lines in output order, from 1; i counts every event received, from 0, refused
    ones included. A rule breaks the way judge() says, judged on the events let through so
    far. A forbidden, uncertainty or approval rule is reported at its first break; a startup
    rule when its watched event is let through before work starts, or when work starts
    without it. Lines that come out on the same event follow rule order. Rules still open when
    the stream ends are reported then, in rule order: a definition_of_done rule is only known
    then, and names the event that broke it, never refused.

    An event that breaks a block rule is refused: it stays out of record, and the rest of the
    turn is judged as if it never happened. A rule that is already reported keeps refusing
    what breaks it, without a second line.
    """

    def __init__(self, rules: list[Rule], watch: Watch | None = None, threshold: float = THRESHOLD) -> None:
        self.rules = list(rules)
        self.watch = watch if watch is not None else Watch()
        self.threshold = threshold
        self.record: list[Event] = []

    async def run(self, events: AsyncIterator[Event]) -> AsyncIterator[str]:
        raise NotImplementedError
