"""SDK differential: how an SDK's normalized view differs from the raw result on the wire."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .evidence import canonical_json, digest

# JSON Pointer of an object -> members of it the SDK may drop. Only the result root has any.
BOOKKEEPING = {"": frozenset({"resultType", "_meta", "ttlMs", "cacheScope"})}


@dataclass(frozen=True)
class Difference:
    kind: str  # "dropped", "synthesized", "changed" or "lifted"
    path: str  # RFC 6901 JSON Pointer
    to: str | None = None  # where a lifted member went


def sdk_differential(
    raw: Any, sdk: Any, allowed: dict[str, frozenset[str]] = BOOKKEEPING
) -> list[Difference]:
    """Every way the SDK view differs from the raw result, with RFC 6901 JSON Pointer paths
    ("~" written "~0", "/" written "~1"; the root is "").

    Two objects are compared member by member and two lists item by item, by position. Any
    other pair is compared as JSON values, so 1 and "1" differ, and so do a list and an object.

      dropped      the raw view has a member or item the SDK view lacks. allowed maps the
                   pointer of an object to the members the SDK may drop from it, and those
                   drops are not reported. Only dropping is allowed: a bookkeeping member the
                   SDK adds or changes is reported like any other.
      synthesized  the SDK view has a member or item the raw view lacks.
      changed      both have it, with values that differ and are not both objects or both lists.
      lifted       a dropped member and a synthesized member with the same name and equal
                   values, where the synthesized one sits in an ancestor of the dropped one's
                   object, are one lift: Difference("lifted", <dropped path>, to=<new path>).
                   Each member takes part in at most one lift; a dropped member pairs with the
                   first eligible synthesized member in report order.

    Report order: depth first, object members by sorted name, list items by index. A lift is
    reported where its dropped member would have been.
    """
    raise NotImplementedError


def differential_report(
    raw: Any, sdk: Any, allowed: dict[str, frozenset[str]] = BOOKKEEPING
) -> dict[str, Any]:
    """The SDK evidence the release gate takes."""
    differences = sdk_differential(raw, sdk, allowed)
    return {
        "semanticMatch": not differences,
        "differences": [asdict(difference) for difference in differences],
        "rawDigest": digest(raw),
        "sdkDigest": digest(sdk),
    }
