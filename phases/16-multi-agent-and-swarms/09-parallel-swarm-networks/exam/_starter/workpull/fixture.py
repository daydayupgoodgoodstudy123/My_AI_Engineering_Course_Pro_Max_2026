"""Real batched arrivals and an independently assembled complete replay oracle."""
import hashlib
from .models import Task,Worker,Lifecycle,Completion,RunReport

def completion_fixture(count=3000):
    batch_size=250
    tasks=tuple(Task('task-'+str(i),'data','数据-'+str(i),5000*(i//batch_size),1+i%3,i%5,'unused-fixed-owner')for i in range(count))
    worker=Worker('worker-α',('data',));workers=(worker,)
    trace=[];completions=[];cards=[];now=0
    for offset in range(0,len(tasks),batch_size):
        batch=tasks[offset:offset+batch_size]
        trace.extend(Lifecycle('arrival',task.task_id,task.arrival_us,priority=task.priority)for task in batch)
        for task in batch:
            start=max(now,task.arrival_us);end=start+task.duration_us
            value=task.payload[::-1]+':'+hashlib.sha256(task.payload.encode('utf-8')).hexdigest()
            trace.append(Lifecycle('pull',task.task_id,start,worker.uid,start,end,priority=task.priority))
            trace.append(Lifecycle('completion',task.task_id,end,worker.uid,start,end,value))
            completions.append(Completion(task.task_id,worker.uid,start,end,value))
            cards.append((task.task_id,task.topic,task.payload,worker.uid,start,end,value));now=end
    expected=RunReport(tasks,workers,tuple(trace),tuple(completions),((worker.uid,count),),tuple(cards),(),now)
    return(tasks,workers),expected
