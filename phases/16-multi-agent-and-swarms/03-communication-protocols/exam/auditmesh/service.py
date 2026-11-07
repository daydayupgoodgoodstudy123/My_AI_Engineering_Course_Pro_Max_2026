"""GIVEN receipt consumers and a fixed facade; no gateway policy is implemented here."""
from .capture import capture_once

def receipt_consumer(observation):
    entry=observation.audit
    if observation.reply is not None and entry['invocation_id']!=observation.reply['invocation_id']:
        raise ValueError('receipt invocation mismatch')
    return {'ticket':entry['input']['ticket']['id'],'run_id':entry['run_id'],
        'duration_ns':entry['completed_at']-entry['started_at'],'status':entry['status'],
        'output':entry['output'],'trajectory':entry['trajectory'],'error':entry['error']}

def render_receipt(entry):
    return {'ticket':entry['input']['ticket']['id'],'run_id':entry['run_id'],
        'duration_ns':entry['completed_at']-entry['started_at'],'status':entry['status'],
        'output':entry['output'],'trajectory':entry['trajectory'],'error':entry['error']}

class AuditDesk:
    def __init__(self,store,clock):self.store=store;self.clock=clock

    def record(self,run_id,agent,inputs,handler,session_id=None):
        observation=capture_once(self.store,run_id,agent,inputs,handler,self.clock,session_id)
        return receipt_consumer(observation)

    def read_audit(self,run_id):
        return render_receipt(self.store.read(run_id))
