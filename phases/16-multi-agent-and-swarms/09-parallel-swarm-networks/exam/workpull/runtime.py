"""Complete logical event driver. Selectors own task admission/priority/claim policy."""
from .models import Event,Completion,Lifecycle,RunReport
from collections import deque
from .support import Ledger,check_inputs,execute_task,receipt_card,fifo_claims,ReadyView
from .calendar import CompletionCalendar
from .primitives import record_completion,producer_finished
class CompletionDesk:
    def run(self,tasks,workers,execute=execute_task,selector=fifo_claims,aging_interval=1):
        tasks=tuple(tasks);workers=tuple(workers);check_inputs(tasks,workers)
        if type(aging_interval)is not int or aging_interval<=0:raise ValueError('positive aging interval')
        by_id={t.task_id:t for t in tasks};order={t.task_id:i for i,t in enumerate(tasks)}
        calendar=CompletionCalendar(Event(t.arrival_us,i,'arrival',t.task_id)for i,t in enumerate(tasks))
        sequence=len(tasks);future=len(tasks);ready=deque();running={};trace=[];now=0
        ledger=Ledger(counts={w.uid:0 for w in workers})
        while calendar:
            now=calendar.peek_time()
            while calendar and calendar.peek_time()==now:
                event=calendar.pop();task=by_id[event.task_id]
                if event.kind=='arrival':
                    future-=1;ready.append(task);trace.append(Lifecycle('arrival',task.task_id,now,priority=task.priority))
                else:
                    running.pop(event.worker_uid)
                    completion=Completion(task.task_id,event.worker_uid,event.start_us,now,event.value)
                    record_completion(ledger,completion)
                    trace.append(Lifecycle('completion',task.task_id,now,event.worker_uid,event.start_us,now,event.value))
            free=tuple(w for w in workers if w.uid not in running)
            claims=tuple(selector(now,ReadyView(ready),free,order,aging_interval))
            if len(claims)>1 and (len({w.uid for w,t in claims})!=len(claims)or len({t.task_id for w,t in claims})!=len(claims)):raise ValueError('unique simultaneous claims')
            for worker,task in claims:
                if worker not in free or task not in ready:raise ValueError('claim from current ready/free set')
                ready.remove(task);running[worker.uid]=task.task_id
                trace.append(Lifecycle('pull',task.task_id,now,worker.uid,now,now+task.duration_us,priority=task.priority))
                value=execute(task,worker)
                calendar.push(Event(now+task.duration_us,sequence,'completion',task.task_id,worker.uid,now,value));sequence+=1
            if producer_finished(ready,running,future):break
        completed={c.task_id for c in ledger.completions}
        cards=tuple(receipt_card(ledger,t)for t in tasks if t.task_id in completed)
        return RunReport(tasks,workers,tuple(trace),tuple(ledger.completions),tuple(ledger.counts.items()),cards,tuple(t.task_id for t in tasks if t.task_id not in completed),now)
