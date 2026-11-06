"""The lesson's rule checker: one method per check name, scored against a whole turn."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .rules import SEVERITIES, BrokenRule, Rule
from .turn import RELEASE_SCRIPT, TurnTrace

THRESHOLD = 0.7


def normalize(name: str) -> str:
    """A package name in its PEP 503 normalized form: lowercased, with every run of "-", "_"
    and "." replaced by a single "-".

    FastAPI and fastapi, python_dateutil and python-dateutil, zope.interface and
    zope__interface are the same package.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def unapproved_dependencies(trace: TurnTrace) -> list[str]:
    """The dependencies the turn added that no approval names, as written, in the order added.

    An approval names a dependency when the two normalize to the same name.
    """
    approved = {normalize(name) for name in trace.approvals}
    return [dep for dep in trace.added_dependencies if normalize(dep) not in approved]


class RuleChecker:
    """One method per check name in agent-rules.md. Each takes the turn and returns True when
    the turn keeps the rule."""

    def state_file_fresh(self, trace: TurnTrace) -> bool:
        return trace.read_state_file

    def no_release_script_edits(self, trace: TurnTrace) -> bool:
        return RELEASE_SCRIPT not in trace.edited_files

    def tests_pass(self, trace: TurnTrace) -> bool:
        return trace.tests_exit_code == 0

    def opened_question_when_unsure(self, trace: TurnTrace) -> bool:
        return trace.confidence >= THRESHOLD or trace.asked_for_help

    def new_dependency_approved(self, trace: TurnTrace) -> bool:
        return not unapproved_dependencies(trace)


@dataclass(frozen=True)
class Result:
    slug: str
    category: str
    severity: str
    passed: bool


@dataclass(frozen=True)
class Report:
    results: tuple[Result, ...]

    def verdict(self, slug: str) -> Result:
        """The result for one rule. KeyError for a rule the report does not hold."""
        for result in self.results:
            if result.slug == slug:
                return result
        raise KeyError(slug)

    @property
    def aggregate(self) -> str:
        """The most severe level among the failed rules ("block", "warn", "info"), or "pass"."""
        failed = {result.severity for result in self.results if not result.passed}
        return next((level for level in SEVERITIES if level in failed), "pass")


def score(rules: list[Rule], checker: RuleChecker, trace: TurnTrace) -> Report:
    """Run every rule's check against the turn, in rule order.

    A rule whose check is not a public method of the checker raises BrokenRule naming the rule
    and the check, before any check runs: a pointer that no longer resolves is a worse failure
    than a missing rule, and the report would blame the agent for it.
    """
    checks = []
    for rule in rules:
        check = None if rule.check.startswith("_") else getattr(checker, rule.check, None)
        if not callable(check):
            raise BrokenRule(
                f"{rule.slug}: check {rule.check!r} is not a method of {type(checker).__name__}"
            )
        checks.append(check)
    return Report(tuple(
        Result(rule.slug, rule.category, rule.severity, bool(check(trace)))
        for rule, check in zip(rules, checks)
    ))
