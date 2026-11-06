"""Flatten nested multimodal chat messages into the pieces the processor consumes."""
from __future__ import annotations

from dataclasses import dataclass

from .inputs import SAMPLE_RATE, clip_tokens

ROLES = ("system", "user", "assistant", "tool")


@dataclass(frozen=True)
class Piece:
    role: str  # the role of the message the piece belongs to
    kind: str  # "text" or "audio"
    text: str  # the text itself; for audio, the clip's label: "Audio 1", "Audio 2", ...
    tokens: int  # words for text (count_words), audio tokens for audio (inputs.clip_tokens)


def count_words(text: str) -> int:
    """The toy tokenizer: one token per whitespace-separated word."""
    return len(text.split())


def flatten(messages: list[dict]) -> list[Piece]:
    """The text and audio pieces of a conversation, in reading order.

    A message is {"role": one of ROLES, "content": content}. Content is a string, which is one
    text part, or a list of parts:
        {"type": "text", "text": str}
        {"type": "audio", "audio": list of samples, "sampling_rate": 16000}
        {"type": "tool_result", "tool_call_id": str, "content": content}
    so tool results nest, to any depth. Clips are labeled "Audio 1", "Audio 2", ... in reading
    order across the whole conversation.

    Bad input raises ValueError, and the message starts with where the problem is, written like
    messages[3].content[0].content[1]: an unknown role, an unknown part type, text that is not a
    string, or audio that is empty or not at 16000 Hz.
    """
    pieces: list[Piece] = []
    clips = 0

    def walk(content, role: str, where: str) -> None:
        nonlocal clips
        if isinstance(content, str):
            pieces.append(Piece(role, "text", content, count_words(content)))
            return
        if not isinstance(content, list):
            raise ValueError(f"{where}: content must be a string or a list of parts")
        for i, part in enumerate(content):
            here = f"{where}[{i}]"
            kind = part.get("type") if isinstance(part, dict) else None
            if kind == "text":
                if not isinstance(part.get("text"), str):
                    raise ValueError(f"{here}: text must be a string")
                pieces.append(Piece(role, "text", part["text"], count_words(part["text"])))
            elif kind == "audio":
                rate = part.get("sampling_rate")
                if rate != SAMPLE_RATE:
                    raise ValueError(f"{here}: audio must be {SAMPLE_RATE} Hz, got {rate}")
                if not part.get("audio"):
                    raise ValueError(f"{here}: audio has no samples")
                clips += 1
                pieces.append(Piece(role, "audio", f"Audio {clips}", clip_tokens(len(part["audio"]))))
            elif kind == "tool_result":
                walk(part.get("content"), role, f"{here}.content")
            else:
                raise ValueError(f"{here}: unknown part type {kind!r}")

    for i, message in enumerate(messages):
        role = message.get("role")
        if role not in ROLES:
            raise ValueError(f"messages[{i}]: unknown role {role!r}")
        walk(message.get("content"), role, f"messages[{i}].content")
    return pieces


def usage(messages: list[dict]) -> dict[str, int]:
    """Tokens per modality over the whole conversation: {"text": ..., "audio": ...}."""
    totals = {"text": 0, "audio": 0}
    for piece in flatten(messages):
        totals[piece.kind] += piece.tokens
    return totals
