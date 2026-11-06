"""The lesson's two-actor code review: a reviewer checks snippets, a checklist collects the verdicts."""
from __future__ import annotations

from typing import Any

from .runtime import Actor, Message, Runtime

REVIEWS = "reviews"


class ReviewerAgent(Actor):
    """Reviews one snippet per "review" message and publishes the verdict on the reviews topic.

    A review is {"id": int, "code": str}. Its verdict is {"id": the same id, "ok": bool,
    "issues": [...]}, with the issues in the order the checks run. verdicts keeps every verdict
    this reviewer published, as it published it.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.verdicts: list[dict[str, Any]] = []

    def receive(self, message: Message, runtime: Runtime) -> None:
        if message.topic != "review":
            return
        review = message.body
        code = review["code"]
        if not isinstance(code, str):
            raise TypeError(f"snippet {review['id']} is not text")
        issues = []
        if "eval(" in code:
            issues.append("uses eval")
        if "except:" in code:
            issues.append("bare except")
        verdict = {"id": review["id"], "ok": not issues, "issues": issues}
        self.verdicts.append(verdict)
        runtime.publish(self.name, REVIEWS, verdict)


class ChecklistAgent(Actor):
    """Sends every snippet of a "start" message to its partner for review, and collects the
    verdicts it hears on the reviews topic (subscribe it to REVIEWS).

    results maps each snippet's index to {"ok": ..., "issues": sorted issues}. consensus is None
    until every snippet of the latest start has its verdict; then it is True if all of them are
    ok and False otherwise.
    """

    def __init__(self, name: str, partner: str) -> None:
        super().__init__(name)
        self.partner = partner
        self.snippets: list[str] = []
        self.results: dict[int, dict[str, Any]] = {}
        self.consensus: bool | None = None

    def receive(self, message: Message, runtime: Runtime) -> None:
        if message.topic == "start":
            self.snippets = message.body
            self.results = {}
            self.consensus = None
            for index, code in enumerate(self.snippets):
                runtime.send(self.name, self.partner, "review", {"id": index, "code": code})
        elif message.topic == REVIEWS:
            verdict = message.body
            index = verdict.pop("id")
            verdict["issues"].sort()
            self.results[index] = verdict
            if all(r["ok"] for r in self.results.values()):
                self.consensus = True
            if len(self.results) == 3:
                self.consensus = all(r["ok"] for r in self.results.values())
