"""API-facing prompt and replay-answer glue."""
from __future__ import annotations

from .examples import ExampleSelector, build_cot_prompt, example_count, extract_answer


class ExampleService:
    def __init__(self, selector: ExampleSelector) -> None:
        self.selector = selector

    def preview(self, question: str, response: str, num_examples: int | None = None, difficulty: int = 0) -> dict:
        """Build a CoT prompt and extract the replay response's explicit final lexeme."""
        count = example_count(num_examples)
        selected = self.selector.select(question, count, difficulty)
        system, user = build_cot_prompt(question, selected, count)
        return {"system": system, "user": user, "answer": extract_answer(response),
                "example_ids": [row["id"] for row in selected]}
