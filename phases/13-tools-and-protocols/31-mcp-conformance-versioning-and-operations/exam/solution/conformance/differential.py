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


@dataclass(frozen=True)
class _Found:
    kind: str
    path: str
    parent: str | None  # pointer of the object holding the member; None for a list item
    name: str | None
    value: Any


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
    found: list[_Found] = []
    _compare(raw, sdk, "", allowed, found)
    return _pair_lifts(found)


def _pointer(parent: str, token: str | int) -> str:
    return parent + "/" + str(token).replace("~", "~0").replace("/", "~1")


def _same(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def _compare(raw: Any, sdk: Any, path: str, allowed: dict[str, frozenset[str]], found: list[_Found]) -> None:
    if isinstance(raw, dict) and isinstance(sdk, dict):
        may_drop = allowed.get(path, frozenset())
        for name in sorted(raw.keys() | sdk.keys()):
            child = _pointer(path, name)
            if name not in sdk:
                if name not in may_drop:
                    found.append(_Found("dropped", child, path, name, raw[name]))
            elif name not in raw:
                found.append(_Found("synthesized", child, path, name, sdk[name]))
            else:
                _compare(raw[name], sdk[name], child, allowed, found)
    elif isinstance(raw, list) and isinstance(sdk, list):
        for index in range(max(len(raw), len(sdk))):
            child = _pointer(path, index)
            if index >= len(sdk):
                found.append(_Found("dropped", child, None, None, raw[index]))
            elif index >= len(raw):
                found.append(_Found("synthesized", child, None, None, sdk[index]))
            else:
                _compare(raw[index], sdk[index], child, allowed, found)
    elif not _same(raw, sdk):
        found.append(_Found("changed", path, None, None, None))


def _pair_lifts(found: list[_Found]) -> list[Difference]:
    taken: set[int] = set()
    lifts: dict[int, str] = {}
    for i, drop in enumerate(found):
        if drop.kind != "dropped" or drop.parent is None:
            continue
        for j, add in enumerate(found):
            if (
                j not in taken
                and add.kind == "synthesized"
                and add.parent is not None
                and add.name == drop.name
                and drop.parent.startswith(add.parent + "/")
                and _same(add.value, drop.value)
            ):
                taken.add(j)
                lifts[i] = add.path
                break
    report: list[Difference] = []
    for i, item in enumerate(found):
        if i in taken:
            continue
        if i in lifts:
            report.append(Difference("lifted", item.path, lifts[i]))
        else:
            report.append(Difference(item.kind, item.path))
    return report


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
