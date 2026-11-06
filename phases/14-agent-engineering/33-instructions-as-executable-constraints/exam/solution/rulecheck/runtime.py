"""Enforce the rule set while a turn runs, and report it as TAP."""
from __future__ import annotations

from collections.abc import AsyncIterator

from .checker import THRESHOLD, normalize
from .rules import Rule
from .timeline import CHANGES, Watch, watchers
from .turn import TOOL_KINDS, Event


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
        self._match = watchers(self.rules, self.watch)

    async def run(self, events: AsyncIterator[Event]) -> AsyncIterator[str]:
        rules, match = self.rules, self._match
        startup = [k for k, rule in enumerate(rules) if rule.category == "startup"]
        reported: set[int] = set()
        seen: set[int] = set()
        asked = {k: False for k, rule in enumerate(rules) if rule.category == "uncertainty"}
        proof: dict[int, tuple[int, int | None]] = {}
        stale: dict[int, int] = {}
        approved: set[str] = set()
        working = False
        number = 0
        index = -1
        async for event in events:
            index += 1
            starts = (not working and event.kind in TOOL_KINDS
                      and not any(match[k](event) for k in startup))
            broken = []
            for k, rule in enumerate(rules):
                watched = match[k](event)
                if rule.category == "startup":
                    hit = starts and k not in seen
                elif rule.category == "forbidden":
                    hit = watched
                elif rule.category == "uncertainty":
                    hit = watched and event.confidence < self.threshold and not asked[k]
                elif rule.category == "approval":
                    hit = watched and normalize(event.subject) not in approved
                else:
                    hit = False
                if hit:
                    broken.append(k)
            out: list[tuple[int, str, str]] = []
            for k in broken:
                if k not in reported:
                    reported.add(k)
                    refused = " refused" if rules[k].severity == "block" else ""
                    out.append((k, "not ok", f" # event {index}{refused}"))
            if not any(rules[k].severity == "block" for k in broken):
                self.record.append(event)
                working = working or starts
                for k, rule in enumerate(rules):
                    watched = match[k](event)
                    if rule.category == "startup":
                        if watched and not working and k not in seen:
                            seen.add(k)
                            if k not in reported:
                                reported.add(k)
                                out.append((k, "ok", ""))
                    elif rule.category == "uncertainty":
                        if watched:
                            asked[k] = False
                        elif event.kind == "ask":
                            asked[k] = True
                    elif rule.category == "definition_of_done":
                        if watched:
                            proof[k] = (index, event.exit_code)
                            stale.pop(k, None)
                        elif event.kind in CHANGES and k in proof and k not in stale:
                            stale[k] = index
                if event.kind == "approve":
                    approved.add(normalize(event.subject))
            for k, status, note in sorted(out):
                number += 1
                yield f"{status} {number} - {rules[k].slug}{note}\n"
        for k, rule in enumerate(rules):
            if k in reported:
                continue
            number += 1
            if rule.category != "definition_of_done":
                yield f"ok {number} - {rule.slug}\n"
            elif k not in proof:
                yield f"not ok {number} - {rule.slug} # end of turn\n"
            elif proof[k][1] != 0:
                yield f"not ok {number} - {rule.slug} # event {proof[k][0]}\n"
            elif k in stale:
                yield f"not ok {number} - {rule.slug} # event {stale[k]}\n"
            else:
                yield f"ok {number} - {rule.slug}\n"
        yield f"1..{len(rules)}\n"
