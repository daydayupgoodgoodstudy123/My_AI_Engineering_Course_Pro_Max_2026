"""Skills as named, versioned, executable code, and the library that holds them."""
from __future__ import annotations

import copy
import linecache
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

World = dict[str, Any]


@dataclass(frozen=True)
class Skill:
    """One version of a skill.

    code is Python source that defines run(world); fn is that function, compiled from code.
    version is 1, 2, ... inside a library, and 0 for a draft that is not registered.
    depends_on holds references: "name" means the latest version, "name@v" version v.
    """

    name: str
    version: int
    description: str
    code: str
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    fn: Callable[[World], Any] | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class Run:
    """What happened when a skill ran.

    log has one line per skill that finished: "ran <name> v<version>: <what run returned>".
    When a skill raised, ok is False, failed is "<name>@<version>" and error is the stack trace.
    """

    ok: bool
    log: list[str]
    failed: str | None = None
    error: str | None = None


def parse_ref(ref: str) -> tuple[str, int | None]:
    """Split "name@v" into (name, v) and "name" into (name, None)."""
    name, sep, version = ref.partition("@")
    if not name:
        raise ValueError(f"bad skill reference {ref!r}")
    if not sep:
        return name, None
    if not (version.isascii() and version.isdigit()) or int(version) < 1:
        raise ValueError(f"bad skill reference {ref!r}")
    return name, int(version)


def compile_skill(code: str, label: str) -> Callable[[World], Any]:
    """Compile skill source and return the run(world) function it defines.

    label names the code in stack traces, which show it as File "<skill label>".
    """
    filename = f"<skill {label}>"
    namespace: dict[str, Any] = {}
    exec(compile(code, filename, "exec"), namespace)
    fn = namespace.get("run")
    if not callable(fn):
        raise ValueError(f"skill {label} does not define run(world)")
    linecache.cache[filename] = (len(code), None, code.splitlines(True), filename)
    return fn


class SkillLibrary:
    """Named, versioned, executable skills.

    Registering a name that is already taken refines the skill: the new code becomes the
    next version. Every earlier version stays in the library exactly as it was registered
    (code, description, tags, dependencies) and stays executable, so a parent pinned to
    name@1 keeps running version 1 after the skill is refined.

    A library grows to tens of thousands of skills, so register does the work search
    needs up front: it keeps the words of each skill's latest description, and an index
    from each tag to the names of the skills whose latest version carries that tag.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[Skill]] = {}
        self._words: dict[str, frozenset[str]] = {}
        self._tagged: dict[str, set[str]] = {}

    def register(
        self,
        name: str,
        description: str,
        code: str,
        tags: str | Iterable[str] = (),
        depends_on: Iterable[str] = (),
    ) -> Skill:
        """Add a skill, or refine it if the name is taken, and return the new version.

        tags is one tag or an iterable of tags. Every dependency must already be in the
        library; an unknown skill or version raises KeyError.
        """
        tags = (tags,) if isinstance(tags, str) else tuple(tags)
        depends_on = tuple(depends_on)
        for ref in depends_on:
            self.get(*parse_ref(ref))
        version = len(self._versions.get(name, ())) + 1
        skill = Skill(
            name, version, description, code, tags, depends_on,
            compile_skill(code, f"{name} v{version}"),
        )
        if version > 1:
            for tag in self._versions[name][-1].tags:
                self._tagged[tag].discard(name)
        for tag in tags:
            self._tagged.setdefault(tag, set()).add(name)
        self._words[name] = frozenset(description.lower().split())
        self._versions.setdefault(name, []).append(skill)
        return skill

    def draft(self, name: str, code: str, depends_on: Iterable[str] = ()) -> Skill:
        """An unregistered version of a skill (version 0), compiled, for trying out with execute.

        Its dependencies must already be in the library. Code that does not compile raises here.
        """
        depends_on = tuple(depends_on)
        for ref in depends_on:
            self.get(*parse_ref(ref))
        return Skill(name, 0, "", code, (), depends_on, compile_skill(code, f"{name} draft"))

    def get(self, name: str, version: int | None = None) -> Skill:
        """A version of a skill, the latest when version is None.

        Unknown names and versions raise KeyError.
        """
        versions = self._versions.get(name)
        if not versions:
            raise KeyError(name)
        if version is None:
            return versions[-1]
        if not 1 <= version <= len(versions):
            raise KeyError(f"{name}@{version}")
        return versions[version - 1]

    def versions(self, name: str) -> list[Skill]:
        """Every version of a skill, oldest first."""
        if name not in self._versions:
            raise KeyError(name)
        return list(self._versions[name])

    def names(self) -> list[str]:
        return sorted(self._versions)

    def search(
        self, query: str, top_k: int = 3, tag_filter: str | None = None
    ) -> list[tuple[float, Skill]]:
        """Skills ranked by word overlap (Jaccard) between query and description.

        Only the latest version of each skill is searched, so a skill appears once.
        tag_filter keeps the skills that carry exactly that tag, and a filtered search
        scores only the skills the tag index lists, never the rest of the library.
        Skills that share no word with the query are left out; equal scores go to the
        alphabetically first name.
        """
        words = set(query.lower().split())
        names = self._versions if tag_filter is None else self._tagged.get(tag_filter, ())
        scored: list[tuple[float, Skill]] = []
        for name in names:
            described = self._words[name]
            overlap = len(words & described)
            if overlap:
                scored.append((overlap / len(words | described), self._versions[name][-1]))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return scored[:top_k]

    def execute(self, target: str | Skill, world: World) -> Run:
        """Run a skill after its dependencies, against world, which skills change in place.

        target is a reference ("name" or "name@v") or a draft; dependencies always come from
        the library. Each dependency runs before the skill that needs it, in the order they
        are written, and every skill version runs once even when several skills need it.
        All or nothing: when a skill raises, world is put back exactly as it was before the
        call, and the run reports what ran, which skill failed and the stack trace.
        Unknown skills or versions raise KeyError before anything runs.
        """
        root = target if isinstance(target, Skill) else self.get(*parse_ref(target))
        plan = self._plan(root)
        before = copy.deepcopy(world)
        log: list[str] = []
        for skill in plan:
            try:
                result = skill.fn(world)
            except Exception:
                world.clear()
                world.update(before)
                return Run(False, log, f"{skill.name}@{skill.version}", traceback.format_exc())
            log.append(f"ran {skill.name} v{skill.version}: {result}")
        return Run(True, log)

    def _plan(self, root: Skill) -> list[Skill]:
        """root's dependencies, each before the skills that need it, then root; each version once."""
        plan: list[Skill] = []
        done: set[tuple[str, int]] = set()
        active: set[tuple[str, int]] = set()

        def visit(skill: Skill) -> None:
            key = (skill.name, skill.version)
            if key in done:
                return
            if key in active:
                raise ValueError(f"dependency cycle through {skill.name}@{skill.version}")
            active.add(key)
            for ref in skill.depends_on:
                visit(self.get(*parse_ref(ref)))
            active.discard(key)
            done.add(key)
            plan.append(skill)

        visit(root)
        return plan
