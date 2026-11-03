"""The pin manifest: every approved descriptor digest, in one JSON snapshot file."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

FORMAT = "poisonguard-pins/1"
_HEX64 = re.compile(r"[0-9a-fA-F]{64}")


@dataclass(frozen=True)
class Pin:
    key: str  # qualified name, server.tool
    digest: str  # lowercase hex SHA-256 of the approved descriptor (scanner.descriptor_digest)
    publisher: dict[str, str]  # publisher evidence: registry, package, version, signer, ...
    approved_at: datetime  # timezone-aware
    quarantined_at: datetime | None = None  # timezone-aware; set by a rug pull, cleared by approval


class PinStore:
    """Approved pins, kept in one JSON manifest file.

    Several processes share the manifest: the gateway quarantines pins while it refreshes, and the
    review tool approves them. Every call works on the file as it is now, so no store ever writes
    back a stale copy over another writer's change.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)

    def pins(self) -> dict[str, Pin]:
        """Every pin, keyed by qualified name.

        A manifest that does not exist yet holds no pins. A manifest that cannot be read raises
        ValueError: it must never pass for an empty one.
        """
        return self._load()

    def get(self, key: str) -> Pin:
        """The pin under a qualified name. Unknown names raise KeyError."""
        return self._load()[key]

    def approve(self, key: str, digest: str, publisher: dict[str, str], at: datetime) -> Pin:
        """Pin a reviewed descriptor's digest under its qualified name, replacing any earlier pin.

        Qualified names are case-sensitive: notes.Export and notes.export are two different tools.
        The digest is 64 hex digits in either case and is kept lowercase. A key that is not
        server.tool, any other digest, or an approval time without a timezone raises ValueError.
        Approving a quarantined pin again lifts the quarantine.
        """
        _check_key(key)
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise ValueError(f"a digest is 64 hex digits, got {digest!r}")
        _check_time(at)
        pin = Pin(key, digest.lower(), dict(publisher), at, None)
        pins = self._load()
        pins[key] = pin
        self._save(pins)
        return pin

    def quarantine(self, key: str, at: datetime) -> Pin:
        """Quarantine a pin as of `at` (timezone-aware) until it is approved again.

        A pin that is already quarantined keeps the time of its first quarantine.
        Unknown names raise KeyError.
        """
        _check_time(at)
        pins = self._load()
        pin = pins[key]
        if pin.quarantined_at is None:
            pin = replace(pin, quarantined_at=at)
            pins[key] = pin
            self._save(pins)
        return pin

    def _load(self) -> dict[str, Pin]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            data = json.loads(text)
            if data["format"] != FORMAT:
                raise ValueError(f"unknown manifest format {data['format']!r}")
            pins = {}
            for key, entry in data["pins"].items():
                quarantined = entry["quarantined_at"]
                pins[key] = Pin(
                    key,
                    entry["digest"],
                    dict(entry["publisher"]),
                    _parse_time(entry["approved_at"]),
                    None if quarantined is None else _parse_time(quarantined),
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"pin manifest {self.path} cannot be read") from exc
        return pins

    def _save(self, pins: dict[str, Pin]) -> None:
        data = {
            "format": FORMAT,
            "pins": {
                key: {
                    "digest": pin.digest,
                    "publisher": pin.publisher,
                    "approved_at": pin.approved_at.isoformat(),
                    "quarantined_at": None if pin.quarantined_at is None else pin.quarantined_at.isoformat(),
                }
                for key, pin in sorted(pins.items())
            },
        }
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        # Write a temporary file next to the manifest, then swap it in: a crash mid-write
        # leaves the previous manifest whole.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def _check_key(key: str) -> None:
    server, dot, tool = key.partition(".") if isinstance(key, str) else ("", "", "")
    if not server or not dot or not tool or "." in tool:
        raise ValueError(f"pins are kept under qualified names server.tool, got {key!r}")


def _check_time(at: datetime) -> None:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError(f"times must be timezone-aware datetimes, got {at!r}")


def _parse_time(text: str) -> datetime:
    at = datetime.fromisoformat(text)
    _check_time(at)
    return at
