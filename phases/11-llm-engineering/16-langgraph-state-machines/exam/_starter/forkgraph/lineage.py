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
    raise NotImplementedError
