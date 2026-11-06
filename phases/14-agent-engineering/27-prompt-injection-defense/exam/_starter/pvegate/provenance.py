"""Source-tag tracking: which tool arguments were copied from content the user never wrote."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .content import Content
from .gate import ToolCall, Verdict


def tainted_args(args: dict[str, Any], history: list[Content], min_run: int = 8) -> list[str]:
    """Names of the arguments that carry text copied from tainted content, in argument order.

    An argument is tainted when one of its strings, at any depth inside list items and dict
    values, has a window of min_run consecutive characters that occurs in some tainted content of
    the history and in no untainted content. Windows are compared casefolded on both sides.
    Shorter strings and non-string values are never tainted.
    """
    raise NotImplementedError


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
        raise NotImplementedError
