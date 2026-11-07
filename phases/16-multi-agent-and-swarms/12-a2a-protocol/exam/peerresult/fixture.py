"""Real finite task timelines and an independently constructed complete batch result."""
from .models import Artifact,TaskEnvelope,PollRequest,BatchResult
from .transport import LocalTransport
PEER='http://review-peer.local/tasks'
def wire(tid,state,artifact=None):
    return {'id':tid,'state':state,'artifact':None if artifact is None else {'type':artifact.type,'data':artifact.data}}
def polling_fixture(count=400,rounds=500):
    tasks={};requests=[];expected=[]
    for i in range(count):
        tid=f'review-{i:04d}';data={'issues':[f'case {i}: declared review observation'],'lines':i%17+1};artifact=Artifact('structured',data)
        tasks[tid]=((0,wire(tid,'completed',artifact)),);requests.append(PollRequest(tid,PEER,rounds+2));expected.append(TaskEnvelope(tid,'completed',artifact,0))
    tasks['slow']=((0,wire('slow','working')),(rounds,wire('slow','completed',Artifact('text','review finished'))))
    requests.append(PollRequest('slow',PEER,rounds+2));expected.append(TaskEnvelope('slow','completed',Artifact('text','review finished'),rounds))
    tasks['rejected']=((0,wire('rejected','failed',Artifact('text','unknown skill'))),)
    requests.append(PollRequest('rejected',PEER,rounds+2));expected.append(TaskEnvelope('rejected','failed',Artifact('text','unknown skill'),0))
    tasks['never']=((0,wire('never','working')),)
    requests.append(PollRequest('never',PEER,3));expected.append(TaskEnvelope('never','timeout',None,3))
    return tuple(requests),LocalTransport({PEER:tasks}),BatchResult(tuple(expected))
def local_card(modalities=('text','structured')):
    return {'name':'code-review-agent','version':'0.1.0','skills':['review-python'],'endpoints':{'tasks':PEER},'auth':{'type':'none'},'modalities':list(modalities),'protocol_version':'a2a-0.3'}
