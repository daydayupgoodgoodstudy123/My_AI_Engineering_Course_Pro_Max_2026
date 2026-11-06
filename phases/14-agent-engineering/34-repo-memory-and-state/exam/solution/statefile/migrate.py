"""Schema migrations for agent_state.json: every schema bump ships with the step that reaches it."""
from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .manager import atomic_write, dump_state
from .schema import STATE_SCHEMA, VersionError, validate

STATE_V1: dict[str, Any] = {
    "$id": "agent_state.v1.schema.json",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "active_task_id", "touched_files", "next_action"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "active_task_id": {"type": ["string", "null"], "pattern": r"^(T-\d{3,}|)$"},
        "touched_files": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
}

STATE_V2: dict[str, Any] = {
    "$id": "agent_state.v2.schema.json",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "active_task_id", "touched_files", "risks", "next_action"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [2]},
        "active_task_id": {"type": ["string", "null"], "pattern": r"^(T-\d{3,}|)$"},
        "touched_files": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
}

SCHEMAS: dict[int, dict[str, Any]] = {1: STATE_V1, 2: STATE_V2, 3: STATE_SCHEMA}
CURRENT_VERSION = 3

Migration = Callable[[dict], dict]


def v1_to_v2(doc: dict) -> dict:
    """blockers becomes risks, an empty list when the file had none."""
    doc["risks"] = doc.pop("blockers", [])
    doc["schema_version"] = 2
    return doc


def v2_to_v3(doc: dict) -> dict:
    """"" and null both meant "no active task"; v3 keeps null only. last_human_touch starts unknown."""
    if doc["active_task_id"] == "":
        doc["active_task_id"] = None
    doc["last_human_touch"] = None
    doc["schema_version"] = 3
    return doc


# migrations[n] turns a version n document into a version n + 1 document. Like any migration
# script, a step may change the document it is given.
MIGRATIONS: dict[int, Migration] = {1: v1_to_v2, 2: v2_to_v3}


def migrate(
    doc: dict,
    target: int = CURRENT_VERSION,
    *,
    schemas: dict[int, dict[str, Any]] = SCHEMAS,
    migrations: dict[int, Migration] = MIGRATIONS,
) -> dict:
    """Bring a state document to the target version, one step at a time, and return it.

    The document's schema_version must be an int with a schema, no newer than target;
    anything else raises VersionError, as does a missing step: a version this code cannot
    migrate is never loaded. The document is first validated against its own version's
    schema, then every step's result against the next version's schema (schema_version
    included), so a step that breaks the document is caught where it does. The steps work
    on a copy: the caller's document never changes, and a document already at target comes
    back as a copy.
    """
    version = doc.get("schema_version") if isinstance(doc, dict) else None
    if type(version) is not int or version not in schemas:
        raise VersionError(f"schema_version {version!r} has no schema")
    if target not in schemas:
        raise VersionError(f"target version {target!r} has no schema")
    if version > target:
        raise VersionError(f"cannot migrate down from version {version} to {target}")
    validate(doc, schemas[version])
    out = copy.deepcopy(doc)
    for v in range(version, target):
        if v not in migrations:
            raise VersionError(f"no migration from version {v} to {v + 1}")
        out = migrations[v](out)
        validate(out, schemas[v + 1])
    return out


def upgrade_file(
    path: Path,
    target: int = CURRENT_VERSION,
    *,
    schemas: dict[int, dict[str, Any]] = SCHEMAS,
    migrations: dict[int, Migration] = MIGRATIONS,
) -> tuple[int, int]:
    """Migrate the state file at path in place. Returns (version found, version now).

    The file is written once, with atomic_write, and only when its version changes. If
    reading, any step or any validation fails, the file is left exactly as it was and the
    error propagates.
    """
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = migrate(doc, target, schemas=schemas, migrations=migrations)
    if out["schema_version"] != doc["schema_version"]:
        atomic_write(path, dump_state(out))
    return doc["schema_version"], out["schema_version"]
