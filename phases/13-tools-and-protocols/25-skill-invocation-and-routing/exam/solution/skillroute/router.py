"""Route invocation requests: eligibility first, then relevance, with an abstain option."""
from __future__ import annotations

import re
from collections.abc import Iterable

from .catalog import SkillMetadata, parse_frontmatter
from .policy import Actor, CorePolicyAdapter, InvocationDecision, InvocationRequest

EXPLICIT_MODES = {
    Actor.HUMAN: "explicit-human",
    Actor.APPLICATION: "programmatic-application",
    Actor.SKILL: "composed-skill",
    Actor.HARNESS: "programmatic-harness",
}
IMPLICIT_MODES = {Actor.MODEL: "implicit-model", Actor.AGENT: "implicit-agent"}


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def relevance_score(query: str, skill: SkillMetadata) -> float:
    """Jaccard similarity between the query's tokens and the skill's name and description tokens."""
    query_tokens = tokens(query)
    skill_tokens = tokens(f"{skill.name} {skill.description}")
    if not query_tokens or not skill_tokens:
        return 0.0
    return len(query_tokens & skill_tokens) / len(query_tokens | skill_tokens)


class Router:
    """Serves many invocation requests against one catalog snapshot.

    entries are the frontmatter blocks discovery found, one SKILL.md each; names are unique.
    """

    def __init__(self, entries: Iterable[str], adapter: CorePolicyAdapter) -> None:
        self.adapter = adapter
        skills = sorted((parse_frontmatter(text) for text in entries), key=lambda skill: skill.name)
        self._skills = skills
        self._by_name = {skill.name: skill for skill in skills}

    def eligible(self, actor: Actor) -> list[str]:
        """Names of the skills this actor may request, sorted: the selection set routing ranks."""
        return [skill.name for skill in self._skills if self.adapter.allows(skill, actor)[0]]

    def route(self, request: InvocationRequest) -> InvocationDecision:
        """Decide one request.

        Explicit channels (human, application, skill, harness) name the skill: look it up
        and apply the policy to it. Naming a skill never bypasses the policy.

        Implicit channels (model, agent) route by relevance, in this order:
        1. filter the catalog by the policy for the requesting actor;
        2. score only the eligible skills;
        3. abstain when nothing is eligible or the best score misses policy.model_threshold;
        4. when other eligible skills score within policy.ambiguity_margin of the best one
           (an exact tie always does), the request is ambiguous: activate nothing and list
           them all, best included, in candidates so the host can ask the user;
        5. otherwise activate the best eligible skill.
        """
        actor = request.actor
        policy = self.adapter.policy
        if actor in EXPLICIT_MODES:
            mode = EXPLICIT_MODES[actor]
            if not request.explicit_name:
                return InvocationDecision(False, actor, None, mode, 0.0, "an exact skill name is required")
            skill = self._by_name.get(request.explicit_name)
            if skill is None:
                return InvocationDecision(False, actor, None, mode, 0.0, "named skill was not discovered")
            allowed, reason = self.adapter.allows(skill, actor, request)
            return InvocationDecision(allowed, actor, skill.name, mode, 1.0, reason if allowed else f"blocked by {reason}")
        if actor not in IMPLICIT_MODES:
            return InvocationDecision(False, actor, None, "unsupported-actor", 0.0, f"unknown actor {actor!r} has no activation policy")
        mode = IMPLICIT_MODES[actor]
        if request.explicit_name:
            return InvocationDecision(
                False, actor, None, mode, 0.0, "implicit model or agent routing uses task relevance rather than an exact-name channel"
            )
        if not self._skills:
            return InvocationDecision(False, actor, None, mode, 0.0, "catalog is empty")

        eligible = []
        blocked = set()
        for skill in self._skills:
            allowed, reason = self.adapter.allows(skill, actor, request)
            if allowed:
                eligible.append((skill, reason))
            else:
                blocked.add(reason)
        if not eligible:
            reason = "no discovered skill is eligible for implicit routing"
            if blocked:
                reason = f"{reason}: {'; '.join(sorted(blocked))}"
            return InvocationDecision(False, actor, None, mode, 0.0, reason)

        scored = [(relevance_score(request.query, skill), skill, reason) for skill, reason in eligible]
        score, selected, eligibility_reason = max(scored, key=lambda item: (item[0], item[1].name))
        if score < policy.model_threshold:
            return InvocationDecision(False, actor, selected.name, mode, round(score, 4), "best match did not meet the host threshold")
        close = sorted(skill.name for other, skill, _ in scored if score - other <= policy.ambiguity_margin)
        if len(close) > 1:
            return InvocationDecision(
                False, actor, None, mode, round(score, 4), f"ambiguous between {', '.join(close)}", tuple(close)
            )
        return InvocationDecision(True, actor, selected.name, mode, round(score, 4), eligibility_reason)
