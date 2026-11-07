"""Candidate ordered actual observer-local JSON Patch field projection."""
from .wire_support import admitted_deltas,operation_kind,logical_path,patch_value
def patch_operations(batch):
    """Preserve every admitted ordered operation, its own complete path and own typed value, omitting value only for remove."""
    operations=[]
    for delta in admitted_deltas(batch):
        op=operation_kind(delta);row={'op':op,'path':logical_path(delta.key)}
        if op=='replace':row['value']=patch_value(delta)
        operations.append(row)
    return operations
