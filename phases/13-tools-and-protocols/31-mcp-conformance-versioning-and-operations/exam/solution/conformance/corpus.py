"""Golden and negative transcript fixtures, one JSON file per case."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .wire import ERAS

# Volatile members and the value a fixture stores for them.
VOLATILE = {
    "taskId": "task-0",
    "createdAt": "1970-01-01T00:00:00Z",
    "lastUpdatedAt": "1970-01-01T00:00:00Z",
}


@dataclass(frozen=True)
class Transcript:
    """One recorded exchange, and what the case expects of it.

    headers are the request headers as captured: original names, and two names that differ
    only in case stay two headers. response_body is the parsed JSON body, or None when the
    response had no body. expect is None for a golden case (the response is accepted), an int
    for a negative case the server must refuse with that JSON-RPC error code, or a rule name
    from wire.RULES for a negative case whose response must break that rule.
    """

    name: str
    era: str
    headers: dict[str, str]
    request: dict[str, Any]
    response_status: int
    response_body: Any
    capabilities: frozenset[str] = frozenset()
    expect: int | str | None = None


def fixture_filename(name: str) -> str:
    """The file a case lives in.

    The name lowercased, every run of characters other than a-z and 0-9 turned into one "-",
    no "-" at either end, then ".json". A name with no letters or digits is a ValueError.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"case name {name!r} has no letters or digits")
    return slug + ".json"


def normalize_volatile(transcript: Transcript) -> Transcript:
    """Return a copy with volatile values replaced, so re-recording the same behaviour gives the
    same fixture.

    In the request and in the response body, at any depth, the value of every member named in
    VOLATILE becomes VOLATILE[name], but only when it is a non-empty string. Any other value
    (an empty string, a number, null) is what a negative case recorded, and it stays as it is.
    The transcript passed in is not changed.
    """
    return replace(
        transcript,
        request=_normalize(transcript.request),
        response_body=_normalize(transcript.response_body),
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: VOLATILE[key]
            if key in VOLATILE and isinstance(item, str) and item
            else _normalize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


class TranscriptCorpus:
    """A directory of transcript fixtures, one JSON file per case.

    A file holds {"name", "era", "capabilities", "headers", "request", "responseStatus",
    "responseBody", "expect"}: capabilities as a sorted list, responseBody null when the
    response had no body, expect null for a golden case. A hand-written file may leave out
    capabilities and expect. The file name comes from fixture_filename(name); the exact name
    lives inside the file.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, transcript: Transcript) -> Path:
        """Write a transcript, volatile values normalized, and return the file's path.

        Saving a name again replaces its fixture. A name whose file already holds another case
        is refused with ValueError, and that case's file is left alone. An era other than
        "modern" or "legacy" is refused with ValueError.
        """
        if transcript.era not in ERAS:
            raise ValueError(f"unknown era {transcript.era!r}")
        path = self.root / fixture_filename(transcript.name)
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8")).get("name")
            if existing != transcript.name:
                raise ValueError(
                    f"{transcript.name!r} and {existing!r} share the fixture file {path.name}"
                )
        stored = normalize_volatile(transcript)
        record = {
            "name": stored.name,
            "era": stored.era,
            "capabilities": sorted(stored.capabilities),
            "headers": stored.headers,
            "request": stored.request,
            "responseStatus": stored.response_status,
            "responseBody": stored.response_body,
            "expect": stored.expect,
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def load(self, name: str) -> Transcript:
        """The stored case with exactly this name.

        KeyError when there is none. ValueError when its file has no era, or an unknown one:
        the era decides how the response is judged, so it is never guessed.
        """
        path = self.root / fixture_filename(name)
        if not path.exists():
            raise KeyError(name)
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("name") != name:
            raise KeyError(name)
        era = record.get("era")
        if era not in ERAS:
            raise ValueError(f"fixture {name!r} has no valid era: {era!r}")
        return Transcript(
            name=record["name"],
            era=era,
            headers=record["headers"],
            request=record["request"],
            response_status=record["responseStatus"],
            response_body=record["responseBody"],
            capabilities=frozenset(record.get("capabilities", [])),
            expect=record.get("expect"),
        )

    def names(self) -> list[str]:
        """The exact names of the stored cases, sorted."""
        return sorted(
            json.loads(path.read_text(encoding="utf-8"))["name"] for path in self.root.glob("*.json")
        )
