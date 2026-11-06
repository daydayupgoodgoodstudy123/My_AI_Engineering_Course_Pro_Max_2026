"""Flatten SSML markup into segments a synthesizer renders one by one."""
from __future__ import annotations


def flatten(ssml: str) -> list[dict]:
    """Segments of an SSML document, in reading order.

    Supported elements: <speak> (the root, with or without the W3C SSML namespace),
    <prosody rate="150%" pitch="+2st">, <break time="250ms"/> or time="1.5s", and
    <say-as interpret-as="characters|digits|cardinal">.

    A text segment is {"text": str, "rate": float, "pitch": float}. Rate starts at 1.0
    and pitch at 0.0 semitones; an inner <prosody> multiplies the rate and adds to the
    pitch of the prosody around it. Neighbouring text with the same prosody is one
    segment, with each run of whitespace read as one space and the ends stripped.
    A break is {"break_ms": int} and always separates segments. say-as "characters"
    spells the text letter by letter, "digits" reads it one digit at a time, "cardinal"
    reads it as a number. Any other element raises ValueError naming it.
    """
    raise NotImplementedError
