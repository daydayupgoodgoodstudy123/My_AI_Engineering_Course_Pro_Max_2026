"""Immutable per-checkpoint artifacts plus an ordered scoped lineage index."""
from .contracts import checkpoint_key,artifact_path,write_artifact,read_artifact,append_index,read_index,validate_records
class FileCheckpointer:
    def __init__(self,root,writer=write_artifact):self.root=root;self.writer=writer
    def load_all(self):
        """Open every indexed snapshot in order and verify its complete scoped identity.

        Correct full JSON codec, safe artifact paths, atomic artifact writer and
        index framing are GIVEN. Index order is checkpoint commit order. An orphan
        unindexed artifact is ignored; an index must never point at a missing state.
        Records include nested state, reducer version, pending node and parent.
        """
        raise NotImplementedError
    def save(self,row):
        """Persist a complete immutable snapshot before publishing its index key.

        An identical committed retry is idempotent; conflicting same scoped ID
        rejects. Parent must already be committed in this thread. Writer injection
        simulates a local write failure; do not publish an index key if it fails.
        No concurrent-writer durability/fsync/transactional database claim is made.
        """
        raise NotImplementedError
