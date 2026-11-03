"""Constrained decoding: the model may only emit tokens that keep the output valid for a schema."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

EOS = "<eos>"

# The schema becomes a fixed sequence of pieces: ("text", literal), ("enum", JSON literals of
# the members) or ("int", None). A state is (index of the current piece, what it has so far).
Piece = tuple[str, Any]
State = tuple[int, str]


def decode(model: Callable[[str], list[str]], schema: dict) -> Iterator[bytes]:
    """Greedy decoding under a schema, the way grammar-based decoders run open-weights models.

    model(text) takes the JSON text decoded so far and returns candidate next tokens, best
    first; the token EOS ends the output. At every step, take the first candidate that keeps
    the text a prefix of some valid output, yield it at once as UTF-8 bytes, and ask again.
    EOS is allowed only when the output is complete. Once the output is complete and nothing
    can follow it, stop without asking the model again. When no candidate fits, raise ValueError.

    Valid output is the compact JSON text for the schema, with no whitespace:
    - an object has every property, in the order of "properties";
    - a string has an enum and is one of its members, with non-ASCII characters written as
      themselves, not as \\u escapes;
    - an integer has "minimum": 0 and is written without leading zeros.
    Other schemas raise ValueError.
    """
    pieces = _pieces(schema)
    state: State = (0, "")
    text = ""
    while not _complete(pieces, state) or _can_continue(pieces, state):
        for token in model(text):
            if token == EOS:
                if _complete(pieces, state):
                    return
                continue
            after = _advance(pieces, state, token)
            if after is not None:
                break
        else:
            raise ValueError(f"no allowed token after {text!r}")
        state = after
        text += token
        yield token.encode("utf-8")


def _pieces(schema: dict) -> list[Piece]:
    kind = schema.get("type")
    if kind == "object":
        names = list(schema.get("properties", {}))
        if not names:
            return [("text", "{}")]
        pieces: list[Piece] = []
        for i, name in enumerate(names):
            pieces.append(("text", ("," if i else "{") + json.dumps(name, ensure_ascii=False) + ":"))
            pieces.extend(_pieces(schema["properties"][name]))
        pieces.append(("text", "}"))
        return pieces
    if kind == "string" and "enum" in schema:
        return [("enum", tuple(json.dumps(member, ensure_ascii=False) for member in schema["enum"]))]
    if kind == "integer" and schema.get("minimum") == 0:
        return [("int", None)]
    raise ValueError(f"unsupported schema {schema!r}")


def _advance(pieces: list[Piece], state: State, token: str) -> State | None:
    for ch in token:
        state = _step(pieces, state, ch)
        if state is None:
            return None
    return state


def _step(pieces: list[Piece], state: State, ch: str) -> State | None:
    i, typed = state
    while i < len(pieces):
        kind, arg = pieces[i]
        if kind == "text":
            if arg[len(typed)] != ch:
                return None
            typed += ch
            return (i + 1, "") if typed == arg else (i, typed)
        if kind == "enum":
            typed += ch
            if not any(member.startswith(typed) for member in arg):
                return None
            # JSON string literals end at their closing quote, so none is a prefix of another.
            return (i + 1, "") if typed in arg else (i, typed)
        if ch in "0123456789" and typed != "0":
            return (i, typed + ch)
        if not typed:
            return None
        i, typed = i + 1, ""  # the integer has ended; ch starts the next piece
    return None


def _complete(pieces: list[Piece], state: State) -> bool:
    i, typed = state
    return i == len(pieces) or (i == len(pieces) - 1 and pieces[i][0] == "int" and typed != "")


def _can_continue(pieces: list[Piece], state: State) -> bool:
    i, typed = state
    return i < len(pieces) and not (i == len(pieces) - 1 and pieces[i][0] == "int" and typed == "0")
