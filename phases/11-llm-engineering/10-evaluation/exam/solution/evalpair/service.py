"""Given local evaluation service consumes typed judge records and sequence metrics."""
from .judge import build_result
from .metrics import rouge_l_score
class EvalService:
    def evaluate(self,case,output,judge,criteria=None):
        result=build_result(case,output,judge,criteria)
        return {"result":result,"average":result.average_score(),"rouge_l":rouge_l_score(case.reference_output,output)}
