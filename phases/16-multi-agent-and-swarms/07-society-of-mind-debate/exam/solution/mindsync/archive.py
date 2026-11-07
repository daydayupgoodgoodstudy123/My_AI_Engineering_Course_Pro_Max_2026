"""Domain record layout and named answer/confidence vector alignment."""
from .models import FrozenAgent,RoundRecord,DebateArchive
from .binary_support import BinaryWriter,BinaryReader

def save_debate(path,archive):
    """Persist the declared name order and every sealed round, including round0.

    Each record may present agents in a different order. Align answer/confidence
    pairs by agent name, never by that record's temporary position. Scalar and
    optional-truth codecs are complete supplied binary64 primitives.
    """
    with BinaryWriter(path) as writer:
        writer.count(len(archive.names))
        for name in archive.names:writer.text(name)
        writer.count(len(archive.records))
        for record in archive.records:
            writer.index(record.index);writer.optional_scalar(record.truth)
            agents={a.name:a for a in record.agents}
            if set(agents)!=set(archive.names) or len(record.agents)!=len(archive.names):raise ValueError('round agent set mismatch')
            for name in archive.names:
                agent=agents[name];writer.scalar(agent.answer);writer.scalar(agent.confidence)

def load_debate(path):
    """Reopen records in declared name alignment with independent truth metadata."""
    with BinaryReader(path) as reader:
        names=tuple(reader.text() for _ in range(reader.count()));records=[]
        for _ in range(reader.count()):
            index=reader.index();truth=reader.optional_scalar()
            agents=tuple(FrozenAgent(name,reader.scalar(),reader.scalar()) for name in names)
            records.append(RoundRecord(index,agents,truth))
        reader.ensure_end();return DebateArchive(names,tuple(records))
