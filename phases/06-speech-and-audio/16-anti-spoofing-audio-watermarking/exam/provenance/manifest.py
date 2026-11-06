"""C2PA-style provenance manifests for audio, and the ingredient chain behind an asset.

A manifest store maps each manifest's label to the manifest, a JSON-like dict:

    {"claim_generator": "studio/2.1", "assertions": [{"label": ..., "data": {...}}, ...]}

The assertions read here:

    c2pa.hash.data   {"alg": "sha256", "hash": hex}, which binds the manifest to its asset's bytes
    c2pa.actions     {"actions": [{"action": "c2pa.created", "digitalSourceType": iri}, ...]}
    c2pa.ingredient  {"relationship": "parentOf" or "componentOf", "title": ...,
                      "manifest": {"url": label, "hash": hex}}

An ingredient's "manifest" names the ingredient's own manifest in the store, together with the
manifest_hash that manifest had when the ingredient was used. An ingredient that came without
content credentials has no "manifest".
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

TRAINED = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"


def manifest_hash(manifest: dict) -> str:
    """SHA-256 of the manifest as canonical JSON: sorted keys, no whitespace, UTF-8."""
    text = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assertions(manifest: dict, label: str) -> list[dict]:
    """The data of every assertion with this label, in order."""
    return [a["data"] for a in manifest["assertions"] if a["label"] == label]


@dataclass(frozen=True)
class Trace:
    history: list[str]
    ai_generated: bool
    problems: list[str]


def trace(store: dict[str, dict], active: str, asset: bytes) -> Trace:
    """Check the ingredient chain behind an asset, and say where the asset came from.

    Each failed check is reported as "<label>: <code>", label being the manifest that holds the
    assertion that failed:
    - the active manifest's c2pa.hash.data matches the SHA-256 of asset (assertion.dataHash.mismatch);
    - every ingredient that names a manifest finds it in the store (ingredient.manifest.missing),
      still with the hash the ingredient recorded (ingredient.hashedURI.mismatch). A link that
      fails is not followed;
    - a manifest has at most one parentOf ingredient (manifest.multipleParents).
    An ingredient that names a manifest already on the path being followed is a loop, which
    raises ValueError whatever its hash.

    history: the active label, then its parentOf ingredient's label, and so on back to the
    origin. It stops early at a link that fails, or at a manifest with more than one parent.
    ai_generated: the active manifest, or a manifest reached from it through links that hold (by
    either relationship), has an action whose digitalSourceType is TRAINED.
    problems: sorted, each listed once.
    """
    raise NotImplementedError
