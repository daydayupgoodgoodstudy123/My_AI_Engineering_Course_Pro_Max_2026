"""Agent Cards on the calling side: check a card, sign and verify it, discover it, pick a skill."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .model import Message, Task

WELL_KNOWN = "/.well-known/agent.json"
INPUT_MODES = ("text", "file", "data")
OUTPUT_MODES = ("text", "artifact")


class CardError(ValueError):
    """A card the caller must not use."""


@dataclass(frozen=True)
class Choice:
    skill: str  # the id of the skill to send the task to
    delivery: str  # "stream" when the card's capabilities say it can stream, otherwise "poll"


def check_card(card: dict) -> None:
    """Raise CardError, naming the problem, unless the card has the shape the lesson describes:

    - schemaVersion, name, description, url and version are non-empty strings, and url (the A2A
      endpoint) is an absolute https URL;
    - skills is a non-empty list; every skill has a non-empty string id, name and description, an id
      no other skill on the card uses, inputModes drawn from "text", "file" and "data", and
      outputModes drawn from "text" and "artifact" (both lists non-empty);
    - capabilities holds the booleans streaming and pushNotifications.
    Other fields, such as signature, are allowed.
    """
    raise NotImplementedError


def canonical_json(card: dict) -> bytes:
    """The bytes a card's signature covers.

    The card without its "signature" field, as JSON with the keys sorted at every level, no whitespace
    (separators "," and ":"), non-ASCII characters written as themselves rather than as \\u escapes,
    encoded as UTF-8.
    """
    raise NotImplementedError


def sign_card(card: dict, key: bytes, kid: str) -> dict:
    """A signed copy of the card; the card itself is left as it was, and any old signature is replaced.

    The signature field is {"alg": "HS256", "kid": kid, "value": v}, where v is the HMAC-SHA256 of
    canonical_json(card) under key, in base64url without padding.
    """
    raise NotImplementedError


def verify_card(card: dict, keys: dict[str, bytes]) -> bool:
    """True only when the card carries an HS256 signature, under a key id found in keys, that matches
    its canonical JSON. Anything else, a missing or malformed signature included, is False."""
    raise NotImplementedError


def discover(fetch: Callable[[str], bytes], origin: str, keys: dict[str, bytes]) -> dict:
    """Fetch an agent's card from {origin}/.well-known/agent.json and return it.

    origin is the agent's scheme and host, with or without a trailing slash. A card that isn't signed
    by one of keys, or that check_card refuses, raises CardError.
    """
    card = json.loads(fetch(origin.rstrip("/") + WELL_KNOWN))
    if not isinstance(card, dict) or not verify_card(card, keys):
        raise CardError("the card is not signed by a known key")
    check_card(card)
    return card


def choose_skill(card: dict, message: Message, wants: str) -> Choice | None:
    """The first skill on the card, in the card's order, whose inputModes cover the type of every part
    in the message and whose outputModes include wants; None when no skill does.

    A message carries one or more parts: an empty one raises ValueError.
    """
    raise NotImplementedError


def delegate(agent, card: dict, message: Message, wants: str) -> Task | None:
    """Send the message, through agent.tasks_send, to the skill choose_skill picks.

    When no skill fits, nothing is sent and the result is None.
    """
    choice = choose_skill(card, message, wants)
    if choice is None:
        return None
    return agent.tasks_send(choice.skill, message)
