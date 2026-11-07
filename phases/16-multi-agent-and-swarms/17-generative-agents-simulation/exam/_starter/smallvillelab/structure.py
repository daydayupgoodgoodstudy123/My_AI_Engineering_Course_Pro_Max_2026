"""Nested current-time execution with interval, open-hours and shared physical capacity admission."""
from .models import Movement,NodeAudit,ExecutionResult
def execute_nested_plan(roots,world,now):
    """Build every layer report while threading actual movements through one shared simulated world in declaration DFS order."""
    raise NotImplementedError
