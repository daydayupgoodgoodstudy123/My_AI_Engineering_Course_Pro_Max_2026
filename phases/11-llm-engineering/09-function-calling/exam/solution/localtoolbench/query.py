"""Restricted typed table-query tool for the source database-tool exercise."""
from .models import Plan,Bound,OPS,query_shape,require_literal
from .kernel import execute_bound
def compile_query(spec,catalog,allowed):
    """Bind the complete allowlisted query before scanning. Projection order is explicit.

    A missing projection means the full schema; an explicit empty list means empty
    result objects. Duplicate projection fields are rejected. Ordered comparisons support number/string, boolean only '='.
    No coercion, unknown-field fallback, raw SQL or partial query execution.
    """
    query_shape(spec);name=spec["table"]
    if name not in allowed or name not in catalog:raise ValueError("table is not allowed")
    table=catalog[name];fields={name:i for i,(name,kind) in enumerate(table.schema)};predicates=[]
    for condition in spec["filters"]:
        if condition["field"] not in fields or condition["op"] not in OPS:raise ValueError("unknown query field or operator")
        index=fields[condition["field"]];require_literal(table.schema[index][1],condition["value"],condition["op"])
        predicates.append(Bound(index,condition["op"],condition["value"]))
    projection=spec["projection"] if "projection" in spec else [name for name,kind in table.schema]
    if len(set(projection))!=len(projection) or any(name not in fields for name in projection):raise ValueError("unknown projection field")
    return Plan(table,tuple(predicates),tuple(fields[name] for name in projection))
def query_table(spec,catalog,allowed):
    """Execute the complete compiled query through the repaired P1 bound kernel."""
    return execute_bound(compile_query(spec,catalog,allowed))
