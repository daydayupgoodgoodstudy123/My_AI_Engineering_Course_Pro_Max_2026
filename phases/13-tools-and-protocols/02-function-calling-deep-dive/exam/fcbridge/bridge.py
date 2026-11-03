"""Ask one provider one question and get canonical calls back."""
from __future__ import annotations

from typing import Protocol

from .canonical import Call, Tool, ToolChoice
from .translate import PARSERS, tool_fields


class ProviderError(Exception):
    """The provider refused or failed a request (an error status from its API)."""


class Provider(Protocol):
    async def complete(self, request: dict) -> dict:
        """Send one request body to the provider's API and return its reply body."""


class Bridge:
    """The providers this service talks to, by name ("openai", "anthropic", "gemini")."""

    def __init__(self, providers: dict[str, Provider]) -> None:
        self.providers = providers

    async def ask(self, provider: str, tools: list[Tool], prompt: str, choice: ToolChoice) -> list[Call]:
        """Send one user prompt and the tools to one provider, and return the calls it made."""
        request = tool_fields(provider, tools, choice)
        if provider == "gemini":
            request["contents"] = [{"role": "user", "parts": [{"text": prompt}]}]
        else:
            request["messages"] = [{"role": "user", "content": prompt}]
        reply = await self.providers[provider].complete(request)
        return PARSERS[provider](reply)
