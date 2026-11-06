"""Typed source judge assembly using an injected offline criterion fixture."""
from dataclasses import asdict
from .records import EvalResult
DEFAULT_CRITERIA=("relevance","correctness","helpfulness","safety")
def build_result(case,output,judge,criteria=None):
    """Keep each complete typed EvalScore in the in-memory result, in requested order.

    None selects the supplied default rubric; an explicit empty iterable requests
    no criteria. The injected local judge returns EvalScore; it makes no model call.
    """
    selected=DEFAULT_CRITERIA if criteria is None else criteria
    scores=[]
    for criterion in selected:
        score=judge(case,output,criterion)
        scores.append(asdict(score))
    return EvalResult(case.case_id,output,tuple(scores))
