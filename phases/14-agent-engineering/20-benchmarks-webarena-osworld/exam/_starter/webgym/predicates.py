"""Success conditions as nested predicates over the final app state, with an explanation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

Path = tuple[Any, ...]


@dataclass(frozen=True)
class Verdict:
    ok: bool
    blame: Optional[Path] = None


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
    raise NotImplementedError
