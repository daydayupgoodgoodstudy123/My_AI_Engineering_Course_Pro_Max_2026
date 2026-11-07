"""Explicit historical fork selection, independent nested state and declared single updates."""
import copy
from .contracts import validate_delta,checkpoint_key
def choose_checkpoint(book,thread_id,checkpoint_id):
    """Resolve the explicitly requested checkpoint inside its thread."""
    return next(row for row in reversed(book.records) if row.thread_id==thread_id)
def copy_fork_state(state):
    """Give the new branch independent nested state, retaining the original snapshot."""
    return dict(state)
def merge_single(state,delta,reducers):
    """Apply one partial update: append list fields; replace overwrite fields.

    This local append is list concatenation including duplicate values; it is not
    LangGraph add_messages ID replacement or RemoveMessage semantics. No Send
    barrier/order/conflict policy is supplied by this single-update function.
    """
    validate_delta(delta,reducers)
    for key,value in delta.items():
        if reducers[key]=="append":state[key]=copy.deepcopy(value)
        else:state[key]=copy.deepcopy(value)
def ancestry(book,thread_id,checkpoint_id):
    """Return the complete root-to-requested chain along actual scoped parent links.

    Preserve every checkpoint and branch edge; reject an actual repeated ancestor
    on this path. Other branches sharing an ancestor do not form a cycle.
    """
    rows=[];seen=set();current=checkpoint_id
    while current is not None:
        if current in seen:raise ValueError("checkpoint cycle")
        seen.add(current);row=next(row for row in book.records if row.thread_id==thread_id and row.checkpoint_id==current);rows.append(row);current=row.parent_id
    return tuple(reversed(rows))
