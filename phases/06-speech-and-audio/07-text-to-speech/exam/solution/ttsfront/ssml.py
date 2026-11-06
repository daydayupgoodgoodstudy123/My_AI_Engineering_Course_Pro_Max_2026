"""Flatten SSML markup into segments a synthesizer renders one by one."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .normalize import digit_words, number_words

Prosody = tuple[float, float]  # (rate, pitch in semitones)


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
    root = ET.fromstring(ssml)
    if _tag(root) != "speak":
        raise ValueError(f"an SSML document starts with <speak>, not <{_tag(root)}>")
    segments: list[dict] = []
    pending: list[str] = []
    pending_prosody: Prosody | None = None

    def flush() -> None:
        nonlocal pending_prosody
        text = " ".join("".join(pending).split())
        if text:
            rate, pitch = pending_prosody
            segments.append({"text": text, "rate": rate, "pitch": pitch})
        pending.clear()
        pending_prosody = None

    def add_text(text: str | None, prosody: Prosody) -> None:
        nonlocal pending_prosody
        if not text:
            return
        if pending and prosody != pending_prosody:
            flush()
        pending.append(text)
        pending_prosody = prosody

    def walk(element: ET.Element, prosody: Prosody) -> None:
        tag = _tag(element)
        if tag == "break":
            flush()
            segments.append({"break_ms": _break_ms(element.get("time", ""))})
            return
        if tag == "say-as":
            add_text(_say_as(element), prosody)
            return
        if tag == "prosody":
            prosody = _combine(prosody, element)
        elif tag != "speak":
            raise ValueError(f"unsupported SSML element <{tag}>")
        add_text(element.text, prosody)
        for child in element:
            walk(child, prosody)
            # Text after a child's closing tag is back in this element's prosody.
            add_text(child.tail, prosody)

    walk(root, (1.0, 0.0))
    flush()
    return segments


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _combine(prosody: Prosody, element: ET.Element) -> Prosody:
    rate, pitch = prosody
    if "rate" in element.attrib:
        rate *= _percent(element.attrib["rate"])
    if "pitch" in element.attrib:
        pitch += _semitones(element.attrib["pitch"])
    return rate, pitch


def _percent(value: str) -> float:
    if not value.endswith("%"):
        raise ValueError(f"rate must be a percentage such as 150%, got {value!r}")
    factor = float(value[:-1]) / 100
    if factor <= 0:
        raise ValueError(f"rate must be positive, got {value!r}")
    return factor


def _semitones(value: str) -> float:
    if not value.endswith("st"):
        raise ValueError(f"pitch must be in semitones such as +2st, got {value!r}")
    return float(value[:-2])


def _break_ms(value: str) -> int:
    if value.endswith("ms"):
        ms = float(value[:-2])
    elif value.endswith("s"):
        ms = float(value[:-1]) * 1000
    else:
        raise ValueError(f"break time must end in ms or s, got {value!r}")
    if ms < 0:
        raise ValueError(f"negative break time {value!r}")
    return round(ms)


def _say_as(element: ET.Element) -> str:
    if len(element):
        raise ValueError("<say-as> holds text only")
    text = (element.text or "").strip()
    kind = element.get("interpret-as")
    if kind == "characters":
        return " ".join(ch for ch in text if not ch.isspace())
    if kind in ("digits", "cardinal"):
        if not text.isdigit():
            raise ValueError(f"say-as {kind} needs digits, got {text!r}")
        return " ".join(digit_words(text)) if kind == "digits" else number_words(int(text))
    raise ValueError(f"unsupported say-as interpret-as={kind!r}")
