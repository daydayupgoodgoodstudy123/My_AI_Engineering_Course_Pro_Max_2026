"""Execution of fully bound, pure conjunctive table predicates."""
from .models import validate_plan
def matches_row(row,predicates):
    """Return logical AND in declared order; stop after the first false comparison."""
    return all([predicate(row) for predicate in predicates])
def execute_bound(plan):
    """Given complete bound validation, row-order traversal and declared column projection."""
    validate_plan(plan)
    names=[plan.table.schema[i][0] for i in plan.projection]
    return [dict(zip(names,(row[i] for i in plan.projection))) for row in plan.table.rows if matches_row(row,plan.predicates)]
