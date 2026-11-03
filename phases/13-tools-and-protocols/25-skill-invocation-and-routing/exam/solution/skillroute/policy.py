"""Invocation policy: who may start a skill, decided apart from which skill fits."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .catalog import SkillMetadata


class Actor(str, Enum):
    HUMAN = "human"
    MODEL = "model"
    AGENT = "agent"
    APPLICATION = "application"
    SKILL = "skill"
    HARNESS = "harness"


@dataclass(frozen=True)
class InvocationPolicy:
    """Host policy for every channel that can start a skill.

    model_threshold is the relevance an implicit match must reach. ambiguity_margin is
    how close another eligible skill may score before the match counts as ambiguous;
    with the default 0.0 only an exact tie does.
    """

    allow_human: bool = True
    allow_model: bool = True
    allow_agent: bool = True
    allow_programmatic: bool = True
    allow_application: bool = True
    allow_skill: bool = False
    model_threshold: float = 0.2
    ambiguity_margin: float = 0.0
    harness_allowlist: tuple[str, ...] = ()
    application_allowlist: tuple[str, ...] = ()
    skill_caller_allowlist: tuple[str, ...] = ()
    max_skill_depth: int = 1

    def __post_init__(self) -> None:
        for name in ("allow_human", "allow_model", "allow_agent", "allow_programmatic", "allow_application", "allow_skill"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean")
        for name in ("model_threshold", "ambiguity_margin"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be a finite number from 0 to 1")
        for name in ("harness_allowlist", "application_allowlist", "skill_caller_allowlist"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
                raise TypeError(f"{name} must be a tuple of non-empty names")
        if type(self.max_skill_depth) is not int or self.max_skill_depth < 1:
            raise ValueError("max_skill_depth must be a positive integer")


@dataclass(frozen=True)
class InvocationRequest:
    actor: Actor
    query: str
    explicit_name: str | None = None
    caller_name: str | None = None
    depth: int = 0


@dataclass(frozen=True)
class InvocationDecision:
    """The outcome of one request, with the policy or routing reason behind it.

    candidates is filled only for an ambiguous implicit request: the eligible skills the
    host should ask the user to choose from, sorted by name.
    """

    activated: bool
    actor: Actor | str
    skill_name: str | None
    mode: str
    score: float
    reason: str
    candidates: tuple[str, ...] = ()


class CorePolicyAdapter:
    """Apply only the host policy the application supplies; ignore frontmatter extensions."""

    def __init__(self, policy: InvocationPolicy) -> None:
        self.policy = policy

    def allows(self, skill: SkillMetadata, actor: Actor, request: InvocationRequest | None = None) -> tuple[bool, str]:
        if actor is Actor.HUMAN:
            return self.policy.allow_human, "human activation policy"
        if actor is Actor.MODEL:
            return self.policy.allow_model, "model activation policy"
        if actor is Actor.AGENT:
            return self.policy.allow_agent, "agent activation policy"
        if actor is Actor.APPLICATION:
            allowed = self.policy.allow_application and skill.name in self.policy.application_allowlist
            return allowed, "application activation policy and target allowlist"
        if actor is Actor.SKILL:
            if not self.policy.allow_skill:
                return False, "skill composition policy"
            if request is None or not request.caller_name:
                return False, "skill composition requires a caller identity"
            if request.caller_name == skill.name:
                return False, "direct skill self-cycle"
            if request.caller_name not in self.policy.skill_caller_allowlist:
                return False, "skill caller allowlist"
            if request.depth < 1 or request.depth > self.policy.max_skill_depth:
                return False, "skill composition depth limit"
            return True, "skill caller allowlist and depth policy"
        if actor is Actor.HARNESS:
            allowed = self.policy.allow_programmatic and skill.name in self.policy.harness_allowlist
            return allowed, "programmatic activation policy and allowlist"
        return False, f"unknown actor {actor!r} has no activation policy"


def _extension_false(value: object) -> bool:
    return value is False or (isinstance(value, str) and value.lower() == "false")


def _extension_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


class ExtensionPolicyAdapter(CorePolicyAdapter):
    """One host's invocation fields, applied after the core policy allows a request.

    user-invocable: false removes direct human invocation; the model may still select
    the skill. disable-model-invocation: true removes selection by the model and by
    autonomous agents; a human can still invoke the skill by name, and the application,
    skill and harness channels are untouched. A field counts when it is the boolean or
    the text true/false in any case; any other value leaves the default, which allows both.
    """

    def allows(self, skill: SkillMetadata, actor: Actor, request: InvocationRequest | None = None) -> tuple[bool, str]:
        allowed, reason = super().allows(skill, actor, request)
        if not allowed:
            return allowed, reason
        fields = skill.runtime_extensions
        if actor is Actor.HUMAN and _extension_false(fields.get("user-invocable")):
            return False, "host extension user-invocable=false"
        if actor in (Actor.MODEL, Actor.AGENT) and _extension_true(fields.get("disable-model-invocation")):
            return False, "host extension disable-model-invocation=true"
        return True, reason
