"""Given owned in-memory checkpoint catalog and local fixture action dispatch."""
from .contracts import index_records,checkpoint_key,checkpoint_shape,pop_pending,Checkpoint,ForkTrace
from .forks import choose_checkpoint,copy_fork_state,merge_single,ancestry
class MemoryBook:
    def __init__(self,records):
        self.records=list(records);self.by_key=index_records(self.records)
    def commit(self,row):
        checkpoint_shape(row)
        if checkpoint_key(row) in self.by_key:raise ValueError("immutable checkpoint identity")
        if row.parent_id is not None and (row.thread_id,row.parent_id) not in self.by_key:raise ValueError("missing fork parent")
        self.records.append(row);self.by_key[checkpoint_key(row)]=row
    def apply_fork(self,target,request,actions):
        state=copy_fork_state(target.state)
        payload=pop_pending(state,request.action_name)
        delta=actions[request.action_name](payload)
        merge_single(state,delta,target.reducers)
        child=Checkpoint(target.thread_id,request.checkpoint_id,target.checkpoint_id,request.branch_id,"END",target.schema_version,state,dict(target.reducers));self.commit(child);return child
def fork_and_trace(records,request,actions):
    """Complete public path includes catalog index construction, local action, fork and ancestry.

    Inputs are already supplied typed checkpoint records. No SDK, LLM, router,
    interrupt-marker resume, external side effect or prior-node replay is hidden.
    Valid input record parent references exist in the same thread; ancestry cycle
    detection is supplied by the candidate walk, not a repeated whole-graph pass.
    """
    book=MemoryBook(records);target=choose_checkpoint(book,request.thread_id,request.from_id);child=book.apply_fork(target,request,actions)
    return ForkTrace(child,ancestry(book,child.thread_id,child.checkpoint_id),tuple(book.records))
