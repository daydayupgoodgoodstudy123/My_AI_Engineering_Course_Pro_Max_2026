"""Domain record layout and named answer/confidence vector alignment."""
from .models import FrozenAgent,RoundRecord,DebateArchive
from .binary_support import BinaryWriter,BinaryReader

def save_debate(path,archive):
    """Persist the declared name order and every sealed round, including round0.

    Each record may present agents in a different order. Align answer/confidence
    pairs by agent name, never by that record's temporary position. Scalar and
    optional-truth codecs are complete supplied binary64 primitives.
    """
    raise NotImplementedError

def load_debate(path):
    """Reopen records in declared name alignment with independent truth metadata."""
    raise NotImplementedError
