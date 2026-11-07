"""Complete selector input/choice and utterance association snapshots by conversation."""
from .models import Snapshot,Speaker,Utterance
from .support import event_tag
from .db_support import transaction,encode,decode,restore_event,ensure_schema
class ChatArchive:
    def __init__(self,path):
        self.path=path
        with transaction(self.path)as db:ensure_schema(db)
    def save(self,snapshot):
        """Replace only this thread's full audit snapshot, preserving actual declaration order."""
        with transaction(self.path)as db:
            db.execute('DELETE FROM observations WHERE thread=?',(snapshot.thread,))
            db.execute('INSERT OR REPLACE INTO chats VALUES(?,?,?)',(snapshot.thread,encode(tuple((s.name,s.weight,s.active)for s in snapshot.roster)),encode(snapshot.baseline)))
            for position,event in enumerate(snapshot.records):
                if isinstance(event,Utterance):fields=(event.thread,event.message_id,event.speaker,event.content,event.turn,event.decision_id,event.question_id,event.addressee,event.reply_to,event.verdict)
                else:fields=(event.thread,event.decision_id,event.speaker,event.reason,event.context,event.turn,event.accepted,event.private_prompt)
                db.execute('INSERT INTO observations VALUES(?,?,?,?)',(snapshot.thread,position,event_tag(event),encode(fields)))
    def load(self,thread):
        """Reopen exact messages and their decision associations, including each decision's own input."""
        with transaction(self.path)as db:
            row=db.execute('SELECT roster,baseline FROM chats WHERE thread=?',(thread,)).fetchone()
            if row is None:raise KeyError(thread)
            records=tuple(restore_event(kind,decode(payload))for kind,payload in db.execute('SELECT kind,payload FROM observations WHERE thread=? ORDER BY position',(thread,)))
            return Snapshot(thread,tuple(Speaker(*x)for x in decode(row[0])),decode(row[1]),records)
