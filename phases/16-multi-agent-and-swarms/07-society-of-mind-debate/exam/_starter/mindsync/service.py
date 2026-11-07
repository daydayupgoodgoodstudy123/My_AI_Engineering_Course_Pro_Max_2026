"""GIVEN complete local diagnostic desk; performs no debate update."""
from .primitives import report_round
class RoundDesk:
    def record(self,index,agents,truth=None,tol=0.1):
        return report_round(index,agents,truth,tol)
