"""Domain projection of recorded task lifecycle data, never a second scheduler."""
class EventProjection:
    def event_payload(self,event):
        """Keep each observed phase's time/identity and its actual assigned worker/result.

        Arrival carries queued priority. Pull carries real start/finish and actual
        worker; completion carries its real result. No task-duration frame header.
        The supplied driver owns complete UTF8 framing and async transport.
        """
        row={'kind':event.kind,'task_id':event.task_id,'time_us':event.time_us}
        if event.kind=='arrival':row['queued_priority']=event.priority
        elif event.kind=='pull':row.update(worker_uid=event.worker_uid,start_us=event.start_us,finish_us=event.finish_us)
        elif event.kind=='completion':row.update(worker_uid=event.worker_uid,start_us=event.start_us,finish_us=event.finish_us,result=event.value)
        else:raise ValueError('lifecycle kind')
        return row
