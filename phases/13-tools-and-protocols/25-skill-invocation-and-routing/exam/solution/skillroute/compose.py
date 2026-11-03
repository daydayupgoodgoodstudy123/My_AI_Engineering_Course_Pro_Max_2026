"""Skill-to-skill invocation: a tool-like edge the host serves from its own call chain."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any


class Stopped(Exception):
    """Raised inside a skill whose request could not be served and named no fallback."""


@dataclass(frozen=True)
class SkillRequest:
    """What a calling skill must say when it asks for another skill.

    fallback is the value the caller continues with when the target cannot run or does
    not deliver; None means stop. max_depth bounds how deep the chain may go below the
    session's skill, counting this call.
    """

    target_skill: str
    task: str
    inputs: tuple[str, ...] = ()
    expected: str = ""
    reason: str = ""
    fallback: Any = None
    max_depth: int = 1


@dataclass(frozen=True)
class Reply:
    """What a skill hands back: the response contract it fulfils, and the content."""

    contract: str
    body: Any


@dataclass(frozen=True)
class SkillContext:
    """What a running skill gets from the host."""

    skill: str
    task: str
    request: SkillRequest | None  # None for the skill the session started
    visible: tuple[str, ...]  # the conversation context this skill can see
    call: Callable[[SkillRequest], Any]


@dataclass(frozen=True)
class SkillSpec:
    """A skill the host can run. context says how the host activates it for another skill:
    "fork" (a fresh context) or "shared" (the caller's context)."""

    name: str
    run: Callable[[SkillContext], Reply]
    context: str = "fork"


@dataclass(frozen=True)
class Call:
    """One node of the call tree.

    status is "completed", "refused" (it never ran) or "failed" (it ran but did not deliver).
    result is the reply's body for a completed call. used_fallback says that the caller went on
    with the request's fallback. calls are the requests this skill made, in the order made.
    """

    skill: str
    status: str
    detail: str = ""
    result: Any = None
    used_fallback: bool = False
    calls: tuple[Call, ...] = ()


class Composer:
    def __init__(self, skills: Iterable[SkillSpec]) -> None:
        self._skills = {spec.name: spec for spec in skills}

    def run(self, root: str, task: str, context: Sequence[str] = ()) -> Call:
        """Run the session's skill with the conversation context, and return its call tree.

        Inside a running skill, ctx.call(request) asks the host for another skill. The chain is
        the host's own record of the skills running, the session's skill first; a request never
        says who is calling or how deep. The host checks, in this order:
        1. cycle: the target is already on the chain; refused with "cycle: a -> b -> a", the
           chain followed by the target;
        2. depth: the call's depth (1 for a call made by the session's skill) is larger than the
           smallest max_depth among this request and the requests that started every skill on
           the chain; refused with "depth 3 exceeds max_depth 2";
        3. existence: no such skill; refused with "unknown skill <name>".
        Otherwise the target runs. A forked target sees none of its caller's context; a shared
        target sees exactly what its caller sees. Its request is always in ctx.request.

        The call failed when the target's reply carries another contract than expected
        ("expected risk-report.json, got notes.md"; an empty expected accepts any), or when the
        target stopped because one of its own requests failed without a fallback ("stopped").
        A completed call returns the reply's body to the caller. Any other call returns the
        request's fallback when it has one, and otherwise raises Stopped inside the caller.
        Other exceptions from a skill propagate unchanged.
        """
        spec = self._skills.get(root)
        if spec is None:
            return Call(root, "refused", f"unknown skill {root}")
        node, _ = self._start(spec, task, None, tuple(context), ())
        return node

    def _start(self, spec: SkillSpec, task: str, request: SkillRequest | None, visible: tuple[str, ...], chain: tuple) -> tuple[Call, Reply | None]:
        here = chain + ((spec.name, request),)
        children: list[Call] = []

        def call(req: SkillRequest) -> Any:
            child, reply = self._serve(req, visible, here)
            if child.status == "completed":
                children.append(child)
                return reply.body
            if req.fallback is not None:
                children.append(replace(child, used_fallback=True))
                return req.fallback
            children.append(child)
            raise Stopped(f"{req.target_skill}: {child.detail}")

        try:
            reply = spec.run(SkillContext(spec.name, task, request, visible, call))
        except Stopped:
            return Call(spec.name, "failed", "stopped", calls=tuple(children)), None
        return Call(spec.name, "completed", result=reply.body, calls=tuple(children)), reply

    def _serve(self, req: SkillRequest, caller_visible: tuple[str, ...], chain: tuple) -> tuple[Call, Reply | None]:
        names = [name for name, _ in chain]
        if req.target_skill in names:
            return Call(req.target_skill, "refused", "cycle: " + " -> ".join([*names, req.target_skill])), None
        depth = len(chain)
        limit = min([started.max_depth for _, started in chain if started is not None] + [req.max_depth])
        if depth > limit:
            return Call(req.target_skill, "refused", f"depth {depth} exceeds max_depth {limit}"), None
        spec = self._skills.get(req.target_skill)
        if spec is None:
            return Call(req.target_skill, "refused", f"unknown skill {req.target_skill}"), None
        visible = caller_visible if spec.context == "shared" else ()
        node, reply = self._start(spec, req.task, req, visible, chain)
        if reply is None:
            return node, None
        if req.expected and reply.contract != req.expected:
            failed = replace(node, status="failed", detail=f"expected {req.expected}, got {reply.contract}", result=None)
            return failed, None
        return node, reply
