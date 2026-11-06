"""Lock a composed skill to one version of every skill it needs, before it is shared."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .skills import parse_ref

# skill name -> version -> that version's dependency references ("name" or "name@v")
Index = Mapping[str, Mapping[int, Sequence[str]]]


class VersionConflict(ValueError):
    """Two skills in one closure pin different versions of the same skill."""


def resolve(index: Index, ref: str) -> list[str]:
    """Lock ref's closure to one version of each skill, dependencies first.

    Read as written, "name@v" means version v and a bare "name" the latest version. Every
    pin in that tree counts: the lock gives each skill the version it is pinned to, or its
    latest version when nothing pins it, so a bare reference follows a pin made anywhere
    else in the tree. Two different pins for one skill raise VersionConflict naming both
    paths from ref, written like "kit@1 -> pickaxe@1 -> sticks@1". An unknown skill or
    version raises KeyError naming the reference ("sticks@3").

    Returns "name@v" for each skill the locked closure reaches, each after the skills it
    depends on, in the order of a depth-first walk that takes dependencies in the order
    they are written.
    """
    root, root_pin = parse_ref(ref)
    root_version = _version(index, root, root_pin)

    # Walk the tree as written and collect every pin, with the first path that makes it.
    pins: dict[str, tuple[int, str]] = {}
    seen: set[tuple[str, int]] = set()
    todo = [(root, root_version, f"{root}@{root_version}")]
    while todo:
        name, version, path = todo.pop()
        if (name, version) in seen:
            continue
        seen.add((name, version))
        children = []
        for dep in index[name][version]:
            child, pin = parse_ref(dep)
            child_version = _version(index, child, pin)
            child_path = f"{path} -> {child}@{child_version}"
            if pin is not None:
                if child in pins and pins[child][0] != pin:
                    raise VersionConflict(
                        f"{child} is pinned twice: {pins[child][1]} and {child_path}"
                    )
                pins.setdefault(child, (pin, child_path))
            children.append((child, child_version, child_path))
        todo.extend(reversed(children))

    def locked(name: str) -> int:
        return pins[name][0] if name in pins else max(index[name])

    order: list[str] = []
    done: set[str] = set()
    active: set[str] = set()

    def visit(name: str, version: int) -> None:
        if name in done:
            return
        if name in active:
            raise ValueError(f"dependency cycle through {name}")
        active.add(name)
        for dep in index[name][version]:
            child = parse_ref(dep)[0]
            visit(child, locked(child))
        active.discard(name)
        done.add(name)
        order.append(f"{name}@{version}")

    visit(root, root_version)
    return order


def _version(index: Index, name: str, pin: int | None) -> int:
    if name not in index or not index[name]:
        raise KeyError(name if pin is None else f"{name}@{pin}")
    if pin is None:
        return max(index[name])
    if pin not in index[name]:
        raise KeyError(f"{name}@{pin}")
    return pin
