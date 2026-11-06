"""Voyager's automatic curriculum: propose the next task, just above what the library can do."""
from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Recipe:
    """What a task takes: materials it uses up (by count), prerequisite skills, and its value."""

    needs: Mapping[str, int] = field(default_factory=dict)
    requires: tuple[str, ...] = ()
    value: int = 0


@dataclass(frozen=True)
class Gap:
    """What stands between the agent and one task.

    missing: every skill the task needs that the library lacks, the task's own skill
    included, sorted by name. short: how many more of each material the inventory needs for
    the task itself; materials already in hand are left out.
    """

    task: str
    missing: tuple[str, ...]
    short: dict[str, int]


def rank_tasks(
    recipes: Mapping[str, Recipe],
    library: Collection[str],
    inventory: Mapping[str, int],
) -> list[Gap]:
    """The gap of every candidate task, best first.

    A candidate is a task with a recipe whose skill is not in the library yet; Voyager adds
    a skill when it completes a task, so completed tasks are not candidates. Missing skills
    are found by following prerequisites through the skills the library lacks: a skill the
    library has needs nothing more, and a prerequisite with no recipe is missing with
    nothing known below it.

    Best first: the fewest missing skills (one means only the task itself is new, so it is
    just above what the library can do), then tasks whose materials are all in the
    inventory, then the higher value, then the task name.
    """
    have = set(library)
    ranked = []
    for task, recipe in recipes.items():
        if task in have:
            continue
        missing: set[str] = set()
        todo = [task]
        while todo:
            skill = todo.pop()
            if skill in have or skill in missing:
                continue
            missing.add(skill)
            if skill in recipes:
                todo.extend(recipes[skill].requires)
        short = {
            item: count - inventory.get(item, 0)
            for item, count in recipe.needs.items()
            if count > inventory.get(item, 0)
        }
        gap = Gap(task, tuple(sorted(missing)), short)
        ranked.append(((len(missing), bool(short), -recipe.value, task), gap))
    ranked.sort(key=lambda item: item[0])
    return [gap for _, gap in ranked]


def propose(
    recipes: Mapping[str, Recipe],
    library: Collection[str],
    inventory: Mapping[str, int],
) -> Gap | None:
    """The best candidate from rank_tasks, or None when there is no candidate."""
    ranked = rank_tasks(recipes, library, inventory)
    return ranked[0] if ranked else None
