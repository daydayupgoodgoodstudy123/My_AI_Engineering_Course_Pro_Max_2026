"""Thread-scoped common ancestors and branch-specific divergence evidence."""
from .contracts import validate_lineage,Divergence
def compare_branches(records,thread_id,left_id,right_id):
    """Return complete root-to-head paths and suffixes after the nearest common ancestor.

    Given lineage shape/identity/cycle validation allows multiple forks to share
    parents and identical checkpoint spellings in different threads. Follow this
    thread's actual parent links; global commit order is not ancestry. A disconnected
    same-thread root yields common_id None with full paths as both suffixes.
    Shared ancestor is included in paths, excluded from divergence suffixes.
    """
    index=validate_lineage(records)
    def path(head):
        rows=[];current=head
        while current is not None:
            row=index[(thread_id,current)];rows.append(row);current=row.parent_id
        return tuple(reversed(rows))
    left=path(left_id);right=path(right_id);common=None;count=0
    for a,b in zip(left,right):
        if a.checkpoint_id!=b.checkpoint_id:break
        common=a.checkpoint_id;count+=1
    return Divergence(thread_id,common,left,right,left[count:],right[count:])
