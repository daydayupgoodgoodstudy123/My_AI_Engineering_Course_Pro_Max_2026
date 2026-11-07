"""Local trust-gated gateway over corrected capture and persisted observations."""
from copy import deepcopy
from .capture import capture_once
from .models import validate_parts

def validate_declared_output(parts,modes):
    """Accept all and only parts whose tagged MIME modality is declared by the card."""
    validate_parts(parts)
    for part in parts:
        mime='text/plain' if part['kind']=='text' else part['media_type']
        if mime not in modes:return False
    return True

def public_step(step,policy):
    """Project one observed step without exporting private reasoning or arbitrary fields."""
    result={'timestamp':step['timestamp']}
    if 'tool_name' in step:result['tool_name']=step['tool_name']
    if policy.tool_input and 'tool_input' in step:result['tool_input']=deepcopy(step['tool_input'])
    if policy.tool_output and 'tool_output' in step:result['tool_output']=deepcopy(step['tool_output'])
    return result

def project_task_and_public_audit(entry,policy,accepted=True):
    """Derive a task and policy-redacted audit from one persisted run, with no execution."""
    state=entry['status'] if accepted else 'failed'
    task={'id':entry['run_id'],'context_id':entry['session_id'],'state':state,
        'parts':deepcopy(entry['output']) if state=='completed' else [],
        'error':deepcopy(entry['error']) if accepted else {'type':'OutputModeError','message':'undeclared output modality'}}
    audit={key:deepcopy(entry[key]) for key in ('run_id','agent','session_id','status','started_at','completed_at','error')}
    audit['trajectory']=[public_step(step,policy) for step in entry['trajectory']]
    return {'task':task,'audit':audit}

class ProtocolGateway:
    def __init__(self,cards,trust,store,repository,clock,next_id,policy):
        self.cards=cards;self.trust=trust;self.store=store;self.repository=repository
        self.clock=clock;self.next_id=next_id;self.policy=policy

    def delegate(self,caller,agent,inputs,handler,session_id=None):
        """Admit before effects, capture once, persist, validate modes, then project that run."""
        try:admitted=self.trust(caller,agent)
        except Exception:admitted=False
        if not admitted:return {'error':'untrusted caller'}
        if agent not in self.cards:return {'error':'unknown agent'}
        observation=capture_once(self.store,self.next_id(),agent,inputs,handler,self.clock,session_id)
        self.repository.save(observation.audit)
        entry=self.repository.load(observation.audit['run_id'])
        accepted=validate_declared_output(entry['output'],self.cards[agent]['output_modes'])
        return project_task_and_public_audit(entry,self.policy,accepted)
