"""Task arrivals, actual worker claims and completed observations as separate domain records."""
from .models import Task,Worker,Lifecycle,TraceArchive
from .binary_support import append_records,read_records
class TaskJournal:
    def __init__(self,path):self.path=path
    def append(self,tasks=(),workers=(),events=()):
        """Append complete definitions and ordered observed lifecycle records using supplied framing."""
        records=[]
        for t in tasks:records.append(('task',t.task_id,t.topic,t.payload,t.arrival_us,t.duration_us,t.priority,t.pre_assigned))
        for w in workers:records.append(('worker',w.uid,w.topics,w.pool))
        for e in events:records.append(('event',e.kind,e.task_id,e.time_us,e.worker_uid,e.start_us,e.finish_us,e.value,e.priority))
        append_records(self.path,records)
    def load(self):
        """Reopen task/worker definitions and every recorded lifecycle observation in saved order."""
        tasks=[];workers=[];events=[]
        for row in read_records(self.path):
            if row[0]=='task':tasks.append(Task(*row[1:]))
            elif row[0]=='worker':workers.append(Worker(*row[1:]))
            elif row[0]=='event':events.append(Lifecycle(*row[1:]))
            else:raise ValueError('journal domain kind')
        return TraceArchive(tuple(tasks),tuple(workers),tuple(events))
    def task_states(self):
        """Replay actual arrival/pull/completion phases; never infer a completion from an arrival."""
        archive=self.load();states={t.task_id:('not-arrived',None,None,None,None)for t in archive.tasks}
        for e in archive.trace:
            if e.kind=='arrival':states[e.task_id]=('ready',None,None,None,None)
            elif e.kind=='pull':states[e.task_id]=('running',e.worker_uid,e.start_us,None,None)
            elif e.kind=='completion':states[e.task_id]=('complete',e.worker_uid,e.start_us,e.finish_us,e.value)
            else:raise ValueError('lifecycle kind')
        return tuple((t.task_id,)+states[t.task_id]for t in archive.tasks)
