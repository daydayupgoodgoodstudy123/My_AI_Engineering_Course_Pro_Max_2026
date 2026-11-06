"""Source-style typed judge score and evaluation-result records."""
from dataclasses import dataclass
@dataclass(frozen=True)
class EvalCase:
    case_id: str
    input_text: str
    reference_output: object=None
    category: str="general"
@dataclass(frozen=True)
class EvalScore:
    criterion: str
    score: int
    reasoning: str
    max_score: int=5
@dataclass(frozen=True)
class EvalResult:
    test_case_id: str
    model_output: str
    scores: tuple
    model: str="fixture"
    prompt_version: str="v1"
    timestamp: int=0
    def average_score(self):
        """Return the unrounded mean of the supplied scores, or 0.0 for no scores."""
        if not self.scores:return 0.0
        return sum(s.score for s in self.scores)//len(self.scores)
