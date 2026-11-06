"""Select worked examples and construct the lesson's few-shot CoT prompt."""
from __future__ import annotations

import copy
import re


def example_count(num_examples: int | None, default: int = 3) -> int:
    """None selects the default; zero selects no examples; negatives are invalid."""
    count = default if num_examples is None else num_examples
    if type(count) is not int or count < 0:
        raise ValueError("num_examples must be a nonnegative integer")
    return count


class ExampleSelector:
    """Own a corpus of dicts: id/question/reasoning/answer/label/difficulty.

    Token sets are prepared at construction. Ranking is a deterministic local
    proxy for the lesson's similarity/difficulty principles: descending count
    of casefolded whitespace-token overlap, then smaller integer difficulty
    gap, then corpus order. Selection first takes the best example for each
    label in ranking order, then fills from remaining ranked examples. It is
    not an embedding model or a claim about semantic-selection quality.
    """

    def __init__(self, examples: list[dict]) -> None:
        self.examples = copy.deepcopy(examples)
        self._tokens = [frozenset(row["question"].casefold().split()) for row in self.examples]

    def rank(self, question: str, difficulty: int = 0) -> list[int]:
        """Score this query against the whole corpus once and return ranked indices."""
        query = frozenset(question.casefold().split())
        return sorted(range(len(self.examples)), key=lambda i: (
            -len(query & self._tokens[i]), abs(self.examples[i]["difficulty"] - difficulty), i))

    def select(self, question: str, num_examples: int | None = None, difficulty: int = 0) -> list[dict]:
        """Return independent full example records, with one query-scoring pass.

        Preserve label diversity before filling repeated labels. At most the
        corpus size is returned; no example position is selected twice.
        """
        count = example_count(num_examples)
        if count == 0:
            return []
        chosen = []
        used = set()
        seen_labels = set()
        for _ in range(min(count, len(self.examples))):
            ranking = self.rank(question, difficulty)
            diverse = next((i for i in ranking if i not in used and self.examples[i]["label"] not in seen_labels), None)
            index = diverse if diverse is not None else next(i for i in ranking if i not in used)
            chosen.append(index)
            used.add(index)
            seen_labels.add(self.examples[index]["label"])
        return [self.examples[index]["answer"] for index in chosen]


def extract_answer(text: str) -> str | None:
    """Read only the last nonblank line's explicit final-answer marker.

    Markers are case-insensitive 'The answer is' followed by whitespace or a
    colon, or '####' followed by whitespace. Strip one sentence-ending period.
    Return the raw remaining lexeme (numeric validity belongs to the ballot),
    or None. Never fall back to an intermediate arithmetic number.
    """
    match = re.search(r"[+-]?[0-9][0-9,]*(?:\.[0-9]+)?", text)
    return match.group(0) if match is not None else None


def format_example(example: dict) -> str:
    """Format the question, worked reasoning, and final-answer demonstration."""
    return f"Q: {example['question']}\nA: The answer is {example['answer']}.\n\n"


def build_cot_prompt(question: str, examples: list[dict], num_examples: int | None = None) -> tuple[str, str]:
    """Assemble worked CoT demonstrations then the target question, without a model call."""
    count = example_count(num_examples)
    system = ("You are a precise math problem solver. Show your step-by-step reasoning. "
              "State the final answer on the last line as: 'The answer is [number]'.")
    demonstrations = "".join(format_example(row) for row in examples[:count])
    return system, f"{demonstrations}Q: {question}\nA:"
