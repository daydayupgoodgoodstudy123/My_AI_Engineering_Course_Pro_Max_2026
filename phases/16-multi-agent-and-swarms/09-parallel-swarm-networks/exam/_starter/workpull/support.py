"""Complete intake, result reader and per-worker histogram dependencies."""
import hashlib
from itertools import islice
from dataclasses import dataclass,field
from .models import Completion
@dataclass
class Ledger:
    by_task:dict=field(default_factory=dict)
    completions:list=field(default_factory=list)
    counts:dict=field(default_factory=dict)
def check_inputs(tasks,workers):
    if not workers:raise ValueError('at least one worker')
    if len({t.task_id for t in tasks})!=len(tasks) or len({w.uid for w in workers})!=len(workers):raise ValueError('unique task and full worker ids')
    for t in tasks:
        if not isinstance(t.task_id,str)or not t.task_id or not isinstance(t.topic,str)or not isinstance(t.payload,str):raise ValueError('typed task')
        if any(type(n)is not int for n in(t.arrival_us,t.duration_us,t.priority))or t.arrival_us<0 or t.duration_us<0:raise ValueError('nonnegative integer times')
    for w in workers:
        if not isinstance(w.uid,str)or not w.uid or not all(isinstance(t,str)for t in w.topics):raise ValueError('typed worker')
def execute_task(task,worker):
    """Actual local payload transform; no sleep, model or network."""
    return task.payload[::-1]+':'+hashlib.sha256(task.payload.encode('utf-8')).hexdigest()
def increment_worker_histogram(ledger,completion):
    ledger.counts[completion.worker_uid]+=1

def task_result_reader(ledger,task_id):
    return ledger.by_task[task_id]
def receipt_card(ledger,task):
    result=task_result_reader(ledger,task.task_id)
    return(task.task_id,task.topic,task.payload,result.worker_uid,result.start_us,result.finish_us,result.value)
def event_order(event):return(event.time_us,event.sequence)
class ReadyView:
    """Read-only live sequence during one synchronous claim call; tasks are immutable."""
    def __init__(self,ready):self._ready=ready
    def __iter__(self):return iter(self._ready)
    def __len__(self):return len(self._ready)

def fifo_claims(now,ready,free,task_sequence,aging_interval):
    return tuple(zip(free,islice(ready,len(free))))
