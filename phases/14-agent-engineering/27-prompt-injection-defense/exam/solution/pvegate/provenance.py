"""Source-tag tracking: which tool arguments were copied from content the user never wrote."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .content import Content
from .gate import ToolCall, Verdict


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _windows(text: str, n: int) -> set[str]:
    folded = text.casefold()
    return {folded[i : i + n] for i in range(len(folded) - n + 1)}


def tainted_args(args: dict[str, Any], history: list[Content], min_run: int = 8) -> list[str]:
    """Names of the arguments that carry text copied from tainted content, in argument order.

    An argument is tainted when one of its strings, at any depth inside list items and dict
    values, has a window of min_run consecutive characters that occurs in some tainted content of
    the history and in no untainted content. Windows are compared casefolded on both sides.
    Shorter strings and non-string values are never tainted.
    """
    untrusted: set[str] = set()
    trusted: set[str] = set()
    for content in history:
        (untrusted if content.tainted else trusted).update(_windows(content.text, min_run))
    suspect = untrusted - trusted
    return [
        name
        for name, value in args.items()
        if any(_windows(s, min_run) & suspect for s in _strings(value))
    ]


@dataclass
class ProvenanceCheck:
    """The intent and provenance half of the validator.

    intents maps each user intent to the tools that can serve it.
    """

    allowed_tools: tuple[str, ...]
    sensitive_tools: tuple[str, ...]
    intents: dict[str, tuple[str, ...]] = field(default_factory=dict)
    min_run: int = 8

    def assess(self, call: ToolCall, history: list[Content]) -> Verdict:
        """Refuse a tool outside allowed_tools, and a tool that does not serve call.intent
        (an unknown intent serves nothing). A sensitive tool with tainted arguments is refused,
        and the reason names those arguments; a clean one needs a human ("confirm"). Tainted
        arguments to other tools are allowed: searching for what a page says is normal.
        """
        if call.name not in self.allowed_tools:
            return Verdict("refuse", f"tool {call.name!r} not in allowlist")
        if call.name not in self.intents.get(call.intent, ()):
            return Verdict("refuse", f"{call.name!r} does not serve intent {call.intent!r}")
        if call.name in self.sensitive_tools:
            tainted = tainted_args(call.args, history, self.min_run)
            if tainted:
                return Verdict("refuse", "untrusted text in " + ", ".join(repr(a) for a in tainted))
            return Verdict("confirm", f"{call.name!r} is a sensitive tool")
        return Verdict("allow", "ok")
