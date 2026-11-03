"""Agent Cards on the calling side: check a card, sign and verify it, discover it, pick a skill."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

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
    for field in ("schemaVersion", "name", "description", "url", "version"):
        if not _text(card.get(field)):
            raise CardError(f"{field} must be a non-empty string")
    url = urlsplit(card["url"])
    if url.scheme != "https" or not url.netloc:
        raise CardError(f"url must be an absolute https URL, not {card['url']!r}")
    skills = card.get("skills")
    if not isinstance(skills, list) or not skills:
        raise CardError("skills must be a non-empty list")
    seen: set[str] = set()
    for skill in skills:
        if not isinstance(skill, dict):
            raise CardError("every skill must be an object")
        for field in ("id", "name", "description"):
            if not _text(skill.get(field)):
                raise CardError(f"every skill needs a non-empty string {field}")
        if skill["id"] in seen:
            raise CardError(f"skill id {skill['id']!r} is used twice")
        seen.add(skill["id"])
        for field, allowed in (("inputModes", INPUT_MODES), ("outputModes", OUTPUT_MODES)):
            modes = skill.get(field)
            if not isinstance(modes, list) or not modes or any(mode not in allowed for mode in modes):
                raise CardError(f"skill {skill['id']!r} needs {field} drawn from {allowed}")
    capabilities = card.get("capabilities")
    if not isinstance(capabilities, dict) or not all(
        isinstance(capabilities.get(flag), bool) for flag in ("streaming", "pushNotifications")
    ):
        raise CardError("capabilities must hold the booleans streaming and pushNotifications")


def canonical_json(card: dict) -> bytes:
    """The bytes a card's signature covers.

    The card without its "signature" field, as JSON with the keys sorted at every level, no whitespace
    (separators "," and ":"), non-ASCII characters written as themselves rather than as \\u escapes,
    encoded as UTF-8.
    """
    body = {key: value for key, value in card.items() if key != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_card(card: dict, key: bytes, kid: str) -> dict:
    """A signed copy of the card; the card itself is left as it was, and any old signature is replaced.

    The signature field is {"alg": "HS256", "kid": kid, "value": v}, where v is the HMAC-SHA256 of
    canonical_json(card) under key, in base64url without padding.
    """
    mac = hmac.new(key, canonical_json(card), hashlib.sha256).digest()
    value = base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
    return {**card, "signature": {"alg": "HS256", "kid": kid, "value": value}}


def verify_card(card: dict, keys: dict[str, bytes]) -> bool:
    """True only when the card carries an HS256 signature, under a key id found in keys, that matches
    its canonical JSON. Anything else, a missing or malformed signature included, is False."""
    signature = card.get("signature")
    if not isinstance(signature, dict) or signature.get("alg") != "HS256":
        return False
    kid, value = signature.get("kid"), signature.get("value")
    if not isinstance(kid, str) or kid not in keys or not isinstance(value, str):
        return False
    expected = sign_card(card, keys[kid], kid)["signature"]["value"]
    return hmac.compare_digest(expected.encode("ascii"), value.encode("utf-8"))


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
    if not message.parts:
        raise ValueError("a message carries one or more parts")
    needed = {part.type for part in message.parts}
    for skill in card["skills"]:
        if needed <= set(skill["inputModes"]) and wants in skill["outputModes"]:
            delivery = "stream" if card["capabilities"]["streaming"] else "poll"
            return Choice(skill["id"], delivery)
    return None


def delegate(agent, card: dict, message: Message, wants: str) -> Task | None:
    """Send the message, through agent.tasks_send, to the skill choose_skill picks.

    When no skill fits, nothing is sent and the result is None.
    """
    choice = choose_skill(card, message, wants)
    if choice is None:
        return None
    return agent.tasks_send(choice.skill, message)


def _text(value) -> bool:
    return isinstance(value, str) and value != ""
