"""Success conditions as nested predicates over the final app state, with an explanation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

Path = tuple[Any, ...]

# leaf predicate: (required arguments, optional arguments)
LEAVES = {
    "orders": ({"count"}, set()),
    "ordered": ({"sku"}, {"qty"}),
    "price": ({"sku", "eq"}, set()),
    "cart_empty": (set(), set()),
}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    blame: Optional[Path] = None


def _op(node: Any, path: Path) -> tuple[str, Any]:
    if not isinstance(node, dict) or len(node) != 1:
        raise ValueError(f"predicate at {path} must be a dict with one key, got {node!r}")
    ((op, arg),) = node.items()
    return op, arg


def _validate(node: Any, path: Path) -> None:
    op, arg = _op(node, path)
    if op in ("all", "any"):
        if not isinstance(arg, list):
            raise ValueError(f"{op} at {path} takes a list")
        for i, child in enumerate(arg):
            _validate(child, path + (op, i))
    elif op == "not":
        _validate(arg, path + (op,))
    elif op in LEAVES:
        required, optional = LEAVES[op]
        if not isinstance(arg, dict) or not required <= set(arg) <= required | optional:
            raise ValueError(f"bad arguments for {op} at {path}: {arg!r}")
    else:
        raise ValueError(f"unknown predicate {op!r} at {path}")


def _leaf(op: str, arg: dict[str, Any], state: dict[str, Any]) -> bool:
    if op == "orders":
        return len(state["orders"]) == arg["count"]
    if op == "ordered":
        return any(
            arg["sku"] in o["items"] and ("qty" not in arg or o["items"][arg["sku"]] == arg["qty"])
            for o in state["orders"]
        )
    if op == "price":
        return any(row["sku"] == arg["sku"] and row["price"] == arg["eq"] for row in state["catalog"])
    return not state["cart"]


def _holds(node: dict[str, Any], state: dict[str, Any]) -> bool:
    ((op, arg),) = node.items()
    if op == "all":
        return all(_holds(child, state) for child in arg)
    if op == "any":
        return any(_holds(child, state) for child in arg)
    if op == "not":
        return not _holds(arg, state)
    return _leaf(op, arg, state)


def _blame(node: dict[str, Any], state: dict[str, Any], wanted: bool, path: Path) -> Path:
    """Path to the innermost predicate that explains why node is not `wanted`."""
    ((op, arg),) = node.items()
    if op == "not":
        return _blame(arg, state, not wanted, path + ("not",))
    if op == "all" and wanted:
        i = next(i for i, child in enumerate(arg) if not _holds(child, state))
        return _blame(arg[i], state, True, path + ("all", i))
    if op == "any" and not wanted:
        i = next(i for i, child in enumerate(arg) if _holds(child, state))
        return _blame(arg[i], state, False, path + ("any", i))
    return path


def evaluate(goal: dict[str, Any], state: dict[str, Any]) -> Verdict:
    """Evaluate a goal against a final app state (the snapshot layout of ShoppingApp.state()).

    A goal is a one-key dict:
        {"all": [goal, ...]}   every goal holds (an empty all holds)
        {"any": [goal, ...]}   at least one holds (an empty any does not)
        {"not": goal}
        {"orders": {"count": n}}                 the state holds exactly n orders
        {"ordered": {"sku": s, "qty": q}}        some order holds s at exactly q; without
                                                 "qty", at any quantity
        {"price": {"sku": s, "eq": cents}}       the catalog price of s is cents
        {"cart_empty": {}}
    The whole goal is checked first: a malformed node (not a one-key dict, the wrong kind
    of argument, a missing or unknown argument) or an unknown predicate anywhere raises
    ValueError, even in a branch evaluation would never reach.

    A goal that holds gives Verdict(True, None). One that fails gives Verdict(False, blame),
    blame being the path from the root to the innermost predicate that explains the failure:
    ("all", i) and ("any", i) step into a list, ("not",) into a negation, and () is the root.
    A failed all is explained by its first failing child; a failed not by the predicate it
    forbids, explained in turn as something that should not have held; an any that held
    when it should not have is explained by its first child that held. An any with no child
    holding, an all with every child holding, and a leaf are explained by themselves.
    """
    _validate(goal, ())
    if _holds(goal, state):
        return Verdict(True, None)
    return Verdict(False, _blame(goal, state, True, ()))
