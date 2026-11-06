"""Small API-facing glue for prompt previews and conversation construction."""
from __future__ import annotations

from typing import Any

from .prompts import Pattern, build_multi_turn, build_prompt


class PromptService:
    def __init__(self, patterns: dict[str, Pattern]) -> None:
        self.patterns = dict(patterns)

    def preview(self, name: str, variables: dict[str, Any], system_override: str | None = None) -> dict:
        """Return the built prompt for a registered pattern; unknown names raise KeyError."""
        return build_prompt(self.patterns[name], variables, system_override)

    def conversation(self, name: str, turns: list[tuple[str, str]], system_override: str | None = None) -> dict:
        """Return a multi-turn prompt for a registered pattern."""
        return build_multi_turn(self.patterns[name], turns, system_override)
