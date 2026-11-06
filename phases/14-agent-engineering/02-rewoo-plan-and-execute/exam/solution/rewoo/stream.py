"""Run a plan while the planner is still writing it."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator

from .plan import MISSING, REF, Evidence
from .workers import ToolRegistry

STEP_LINE = re.compile(r"#(E\d+)\s*=\s*([A-Za-z_]\w*)\[(.*)\]")
LINE_BREAK = re.compile(r"\r\n|\r|\n")


async def stream_plan(chunks: AsyncIterator[str], tools: ToolRegistry) -> AsyncIterator[str]:
    """Run each step while the planner is still streaming the plan, and yield one record per step.

    The planner writes one step per line, `#E<k> = <tool>[<input>]`; every other line (its
    reasoning, blank lines) is ignored. A line is complete at its newline, or at the end of the
    stream. The input is everything between the first "[" and the last "]" of the line, and the
    tool gets it, with references filled in, as its only argument.

    A step runs as soon as its line is complete and every step it references has evidence. It may
    refer to a step whose line has not arrived yet, and then waits for it. When several steps are
    ready, the one whose line came first runs first. Each step that finishes yields one record:

        #E<k> = <tool>[<input with references filled in>] -> <evidence>\\n

    A tool that fails gives its error text as the evidence. A step that references a failed or
    skipped step is not run: its record reads `-> skipped` and keeps the input as written. A line
    break inside the input or the evidence is written as one space, so every record is one line.

    A second line for an id that was already written raises ValueError. At the end of the stream,
    a step still waiting for an id the plan never wrote raises KeyError naming it, and steps still
    waiting for each other raise ValueError.
    """
    runner = _Runner(tools)
    buffer = ""
    async for chunk in chunks:
        buffer += chunk
        *lines, buffer = buffer.split("\n")
        for line in lines:
            for record in runner.accept(line):
                yield record
    for record in runner.accept(buffer):
        yield record
    runner.finish()


class _Runner:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools
        self.evidence: dict[str, Evidence] = {}
        self.written: set[str] = set()
        self.waiting: list[tuple[str, str, str, list[str]]] = []  # id, tool, input, references; line order

    def accept(self, line: str) -> list[str]:
        match = STEP_LINE.fullmatch(line.strip())
        if match is None:
            return []
        step_id, tool, given = match.groups()
        if step_id in self.written:
            raise ValueError(f"the plan writes {step_id} twice")
        self.written.add(step_id)
        self.waiting.append((step_id, tool, given, [f"E{n}" for n in REF.findall(given)]))
        return self._settle()

    def _settle(self) -> list[str]:
        records = []
        while True:
            for i, (step_id, tool, given, refs) in enumerate(self.waiting):
                if all(ref in self.evidence for ref in refs):
                    del self.waiting[i]
                    records.append(self._run(step_id, tool, given, refs))
                    break
            else:
                return records

    def _run(self, step_id: str, tool: str, given: str, refs: list[str]) -> str:
        if any(self.evidence[ref].status != "ok" for ref in refs):
            self.evidence[step_id] = Evidence("skipped", MISSING)
            return _record(step_id, tool, given, "skipped")
        filled = REF.sub(lambda m: self.evidence[f"E{m.group(1)}"].text, given)
        result = self.tools.call(tool, filled)
        self.evidence[step_id] = result
        return _record(step_id, tool, filled, result.text)

    def finish(self) -> None:
        for step_id, _, _, refs in self.waiting:
            for ref in refs:
                if ref not in self.written:
                    raise KeyError(f"{step_id} refers to {ref}, which the plan never wrote")
        if self.waiting:
            raise ValueError("steps wait on each other: " + ", ".join(w[0] for w in self.waiting))


def _record(step_id: str, tool: str, given: str, result: str) -> str:
    return f"#{step_id} = {tool}[{LINE_BREAK.sub(' ', given)}] -> {LINE_BREAK.sub(' ', result)}\n"
