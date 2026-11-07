"""Independent complete handoff replay fixture and expected receipt report."""
from .models import TransferRequest,Transfer,Note,ReplayReport
def replay_fixture(cycles=2700):
    observations=[];audit=[];receipts=[]
    edges=(('A','B'),('B','C'),('C','A'))
    for i in range(cycles*3):
        sender,target=edges[i%3];request=TransferRequest(str(i),sender,target)
        observations.append(request);event=Transfer(str(i),sender,'handoff',target);audit.append(event);receipts.append(event)
        if i%5==0:
            note=Note(sender,'handoff reviewed '+str(i));observations.append(note);audit.append(note)
    before=len(audit)
    for i,(sender,target)in enumerate((('A','B'),('B','A'),('A','B'))):
        call_id='exit-'+str(i);observations.append(TransferRequest(call_id,sender,target));event=Transfer(call_id,sender,'handoff',target);audit.append(event);receipts.append(event)
    observations.append(Note('A','exit stays recorded'));audit.append(observations[-1])
    first=before+2;expected=ReplayReport('perf',tuple(audit),tuple(receipts),tuple(i>=first for i in range(len(audit))),first)
    return tuple(observations),expected
