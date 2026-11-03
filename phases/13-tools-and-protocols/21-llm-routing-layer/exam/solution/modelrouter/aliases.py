"""Model aliases that name models or other aliases, expanded into one flat fallback chain."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Union

# alias -> its chain, or {"region": region, "chain": chain}. A chain lists model names and
# other aliases, in the order the gateway should try them.
AliasTable = Mapping[str, Union[list[str], dict]]


class AliasError(ValueError):
    """The alias table cannot give this alias a chain."""


class AliasCycle(AliasError):
    """An alias reaches itself. cycle runs from the alias that repeats back to itself."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__("alias cycle: " + " -> ".join(cycle))
        self.cycle = cycle


class UnknownName(AliasError):
    """A name that is neither an alias nor a model."""

    def __init__(self, name: str, path: list[str]) -> None:
        where = f" (in {' -> '.join(path)})" if path else ""
        super().__init__(f"{name!r} is neither an alias nor a model{where}")
        self.name = name
        self.path = path


def expand(
    name: str,
    aliases: AliasTable,
    models: Mapping[str, str],
    *,
    region: str | None = None,
    max_depth: int = 5,
) -> list[str]:
    """The models a name stands for, flattened into the order the gateway should try them.

    models maps every known model to the region it runs in; a model stands for itself. An
    alias's chain is expanded depth first, in chain order, and a model reached twice keeps its
    first place. A region, from the caller or from an alias written as {"region": ...,
    "chain": [...]}, admits only models in that region, for everything reached through it: a
    model must satisfy every region on its way down, so an alias whose region conflicts with an
    outer one adds nothing. A model that is not admitted takes no place, so a later path that
    does admit it can still add it.

    Everything an alias reaches is checked, admitted or not. The alias being expanded is at
    depth 1 and each alias it refers to is one deeper; reaching an alias deeper than max_depth
    raises AliasError. An alias that reaches itself raises AliasCycle, whose cycle lists the
    aliases from the repeated one back to itself, e.g. ["a", "b", "a"]. A name that is neither
    an alias nor a model raises UnknownName. If nothing is admitted, raise AliasError.
    """
    chain: list[str] = []
    placed: set[str] = set()

    def admit(model: str, region: str | None, blocked: bool) -> None:
        if not blocked and (region is None or models[model] == region) and model not in placed:
            placed.add(model)
            chain.append(model)

    def visit(alias: str, path: list[str], region: str | None, blocked: bool) -> None:
        if alias in path:
            raise AliasCycle(path[path.index(alias):] + [alias])
        here = path + [alias]
        if len(here) > max_depth:
            raise AliasError(f"aliases nest deeper than {max_depth}: {' -> '.join(here)}")
        spec = aliases[alias]
        entries = spec["chain"] if isinstance(spec, dict) else spec
        inner = spec.get("region") if isinstance(spec, dict) else None
        if inner is not None:
            if region is not None and inner != region:
                blocked = True
            region = region if region is not None else inner
        for entry in entries:
            if entry in aliases:
                visit(entry, here, region, blocked)
            elif entry in models:
                admit(entry, region, blocked)
            else:
                raise UnknownName(entry, here)

    if name in aliases:
        visit(name, [], region, False)
    elif name in models:
        admit(name, region, False)
    else:
        raise UnknownName(name, [])
    if not chain:
        where = f" in region {region}" if region else ""
        raise AliasError(f"{name} has no model{where}")
    return chain
