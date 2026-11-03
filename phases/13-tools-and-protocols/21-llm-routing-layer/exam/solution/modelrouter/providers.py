"""What the gateway sees of a provider: a reply, or an HTTP error status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


class ProviderError(Exception):
    """A provider answered with an HTTP error status instead of a completion."""

    def __init__(self, model: str, status: int, message: str = "") -> None:
        super().__init__(f"{model} answered {status}" + (f": {message}" if message else ""))
        self.model = model
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Reply:
    """A completion: the text and the token usage the provider reported."""

    model: str
    text: str
    input_tokens: int
    output_tokens: int


class Attempt(NamedTuple):
    """One try: what was tried and the HTTP status it answered (200 when it served)."""

    model: str
    status: int
