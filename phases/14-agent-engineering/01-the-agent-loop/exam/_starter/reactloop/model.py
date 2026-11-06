"""Scripted stand-ins for the model, so everything runs offline and the same way every time."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import random
from collections.abc import AsyncIterator
from typing import Any

from .messages import Message

KEY = b"reactloop-demo-provider"
_TAG = b"rs\x80"


class ProviderError(Exception):
    """The provider refused the request."""


class ScriptedModel:
    """A native-reasoning provider that answers from a script.

    Each script entry is one reply, and every key is optional:

        {"thinking": str or a list of str, "text": str, "tool_calls": [{"name": str, "args": dict}]}

    respond() returns the entry with its thinking joined into one string, plus "reasoning": a fresh
    opaque reasoning item (bytes) that has to travel back with that assistant turn on every later
    request. This stand-in is strict about it on purpose: it refuses a conversation in which an
    assistant turn has lost its item or carries one that changed, so a loop that drops or mangles the
    model's reasoning fails loudly instead of quietly. Items are signed with key, so another
    ScriptedModel with the same key accepts them too, for example after a restart.

    requests holds the messages of every request, issued every reasoning item handed out, and sent the
    number of thinking pieces stream() has yielded so far.
    """

    def __init__(self, script: list[dict[str, Any]], *, key: bytes = KEY, seed: int = 0) -> None:
        self.script = list(script)
        self.key = key
        self.rng = random.Random(seed)
        self.requests: list[list[Message]] = []
        self.issued: list[bytes] = []
        self.sent = 0

    def respond(self, messages: list[Message]) -> dict[str, Any]:
        """Return the next reply for this conversation."""
        self._check(messages)
        reply, _ = self._next()
        return reply

    async def stream(self, messages: list[Message]) -> AsyncIterator[tuple[str, Any]]:
        """The streaming form of respond(): yield ("thinking", piece) for each piece of the reply's
        thinking as the model produces it, then ("reply", reply) with what respond() would return."""
        self._check(messages)
        reply, pieces = self._next()
        for piece in pieces:
            await asyncio.sleep(0)
            self.sent += 1
            yield ("thinking", piece)
        await asyncio.sleep(0)
        yield ("reply", reply)

    def _check(self, messages: list[Message]) -> None:
        self.requests.append(list(messages))
        turn = 0
        for message in messages:
            if message.role != "assistant":
                continue
            turn += 1
            if message.reasoning is None:
                raise ProviderError(f"missing reasoning item for assistant turn {turn}")
            if not self._genuine(message.reasoning):
                raise ProviderError(f"reasoning item of assistant turn {turn} was altered")

    def _next(self) -> tuple[dict[str, Any], list[str]]:
        if not self.script:
            raise ProviderError(f"no scripted reply left for request {len(self.requests)}")
        entry = copy.deepcopy(self.script.pop(0))
        pieces = entry.pop("thinking", [])
        if isinstance(pieces, str):
            pieces = [pieces]
        if pieces:
            entry["thinking"] = "".join(pieces)
        nonce = self.rng.randbytes(9)
        entry["reasoning"] = _TAG + nonce + self._mac(nonce)
        self.issued.append(entry["reasoning"])
        return entry, pieces

    def _mac(self, nonce: bytes) -> bytes:
        return hmac.new(self.key, nonce, hashlib.sha256).digest()[:12]

    def _genuine(self, item: object) -> bool:
        if not isinstance(item, bytes) or len(item) != 24 or not item.startswith(_TAG):
            return False
        return hmac.compare_digest(item[12:], self._mac(item[3:12]))


class ScriptedTextModel:
    """A prompt-based model that answers from a script: each completion in turn, whatever the prompt.

    prompts holds every prompt it was given.
    """

    def __init__(self, completions: list[str]) -> None:
        self.completions = list(completions)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if len(self.prompts) > len(self.completions):
            raise ProviderError(f"no scripted completion left for prompt {len(self.prompts)}")
        return self.completions[len(self.prompts) - 1]
