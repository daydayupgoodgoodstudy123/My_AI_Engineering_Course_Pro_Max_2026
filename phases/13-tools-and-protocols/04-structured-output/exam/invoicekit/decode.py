"""Constrained decoding: the model may only emit tokens that keep the output valid for a schema."""
from __future__ import annotations

from collections.abc import Callable, Iterator

EOS = "<eos>"


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
    raise NotImplementedError
