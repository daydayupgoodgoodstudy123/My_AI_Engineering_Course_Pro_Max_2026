"""Restricted typed table-query tool for the source database-tool exercise."""
from .models import Plan,Bound,OPS,query_shape,require_literal
from .kernel import execute_bound
def compile_query(spec,catalog,allowed):
    """Bind the complete allowlisted query before scanning. Projection order is explicit.

    A missing projection means the full schema; an explicit empty list means empty
    result objects. Duplicate projection fields are rejected. Ordered comparisons support number/string, boolean only '='.
    No coercion, unknown-field fallback, raw SQL or partial query execution.
    """
    raise NotImplementedError
def query_table(spec,catalog,allowed):
    """Execute the complete compiled query through the repaired P1 bound kernel."""
    return execute_bound(compile_query(spec,catalog,allowed))
