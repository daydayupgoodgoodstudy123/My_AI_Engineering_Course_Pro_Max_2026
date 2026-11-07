import asyncio,json
from copy import deepcopy
from itertools import count
from time import perf_counter
import pytest
from auditmesh.models import PublicPolicy
from auditmesh.ownership import AuditStore
from auditmesh.capture import capture_once
from auditmesh.service import AuditDesk
from auditmesh.repository import AuditRepository
from auditmesh.gateway import ProtocolGateway,validate_declared_output,project_task_and_public_audit
from auditmesh.stream import AuditProjection
from auditmesh.stream_support import stream_audit
from auditmesh.did import resolve_relationships

def entry_fixture(run_id='run-001',agent='researcher',session_id='session-001'):
    tick=2**60+1
    return {'run_id':run_id,'agent':agent,'session_id':session_id,
        'input':{'ticket':{'id':'001'},'question':'世界'},
        'output':[{'kind':'data','media_type':'application/json','data':{'ratio':1/3,'zero':-0.0,'big':2**70+3,'flag':False}}],
        'trajectory':[{'timestamp':tick,'tool_name':'lookup','tool_input':{'q':'世界'},'tool_output':None,'reasoning':'private one'},
            {'timestamp':tick-1,'reasoning':'private only'},
            {'timestamp':tick,'tool_name':'lookup','tool_output':{'items':[True,0,1/3,-0.0]}},
            {'timestamp':tick,'tool_name':'lookup','tool_output':None}],
        'status':'completed','started_at':tick-5,'completed_at':tick+5,
        'error':None,'invocation_id':7}

def load_fixture(path):
    repository=AuditRepository(path);entry=entry_fixture();repository.save(entry)
    result=repository.load(entry['run_id']);repository.close();return result

def parse_sse(frame):
    lines=frame.splitlines()
    assert frame.endswith('\n\n') and len(lines)==3, 'each audit SSE frame has one event and one complete JSON data field'
    return lines[0].removeprefix('event: '),json.loads(lines[1].removeprefix('data: '))

def stress_fixture():
    requests=[{'ticket':{'id':f'ticket-{run:03}'},'question':f'compare reference {run}'} for run in range(100)]
    steps=[[{'timestamp':run*100+slot,'tool_name':'lookup','tool_input':{'query':request['question'],'page':slot},
        'tool_output':{'matches':[f'row-{run}-{slot}',f'世界-{slot}']},'reasoning':f'compare candidate {slot}'} for slot in range(10)] for run,request in enumerate(requests)]
    expected=[{'ticket':request['ticket']['id'],'run_id':f'bulk-{run}','duration_ns':3,'status':'completed',
        'output':[{'kind':'text','text':f'answer {run}'}],'trajectory':deepcopy(steps[run]),'error':None} for run,request in enumerate(requests)]
    return requests,steps,expected

@pytest.mark.skip('Part 1')
def test_single_execution_and_private_audit():
    """Repair execute-once capture, owned receipts, failure sealing and complete audit recording."""
    store=AuditStore();desk=AuditDesk(store,count(10,3).__next__);effects=[]
    request={'ticket':{'id':'001'},'question':'local lookup'}
    event={'timestamp':11,'tool_name':'lookup','tool_input':{'q':'local'},'tool_output':{'rows':['a']}}
    def handler(inputs,emit):
        effects.append(inputs['ticket']['id'])
        return {'invocation_id':len(effects),'parts':[{'kind':'text','text':'found'}]}
    receipt=desk.record('run-1','researcher',request,handler,'session-1')
    assert receipt['output']==[{'kind':'text','text':'found'}] and len(effects)==1, 'one delegated operation produces one effect and its own receipt'
    request['ticket'].pop('id')
    assert desk.read_audit('run-1')['ticket']=='001', 'an earlier receipt retains the input accepted at execution time'
    def observing_handler(inputs,emit):
        emit(event)
        return {'invocation_id':1,'parts':[{'kind':'text','text':'observed'}]}
    receipt=desk.record('run-observed','researcher',{'ticket':{'id':'observed'}},observing_handler)
    event['tool_output']['rows'].append('later');receipt['trajectory'][0]['tool_input']['q']='edited'
    stored=store.read('run-observed')
    assert stored['trajectory'][0]['tool_output']=={'rows':['a']} and stored['trajectory'][0]['tool_input']=={'q':'local'}, 'caller and returned snapshot edits do not alter a private observed trajectory'
    def fail(inputs,emit):
        emit({'timestamp':23,'tool_name':'lookup','tool_input':{'q':'missing'}})
        raise LookupError('no local record')
    failed=desk.record('run-failed','researcher',{'ticket':{'id':'missing'}},fail,'session-1')
    assert failed['status']=='failed' and failed['duration_ns']==3 and failed['error']=={'type':'LookupError','message':'no local record'}, 'failed operations retain a bounded receipt and their exact error evidence'
    assert failed['trajectory']==[{'timestamp':23,'tool_name':'lookup','tool_input':{'q':'missing'}}] and len(store.all())==3, 'a failed operation keeps observations made before failure and remains in the audit log'
    requests,steps,expected=stress_fixture();bulk=AuditStore();bulk_desk=AuditDesk(bulk,count(1000,3).__next__);calls=[]
    start=perf_counter();actual=[]
    for run,inputs in enumerate(requests):
        def work(request,emit):
            calls.append(run)
            for step in steps[run]:emit(step)
            return {'invocation_id':run,'parts':[{'kind':'text','text':f'answer {run}'}]}
        actual.append(bulk_desk.record(f'bulk-{run}','researcher',inputs,work,'bulk-session'))
    assert actual==expected and calls==list(range(len(requests))), 'every recorded run retains its complete output and every observed tool slot'
    snapshots=bulk.all()
    assert [(entry['run_id'],entry['input'],entry['output'],entry['trajectory'],entry['invocation_id'],entry['status'],entry['session_id'],entry['started_at'],entry['completed_at'],entry['error']) for entry in snapshots]==[(f'bulk-{run}',requests[run],expected[run]['output'],steps[run],run,'completed','bulk-session',1000+6*run,1003+6*run,None) for run in range(len(requests))], 'the complete private audit includes each original input identity outcome and observation'
    elapsed=perf_counter()-start
    assert elapsed<0.15, 'complete multi-run audit recording remains responsive'
    snapshots[0]['trajectory'][0]['tool_output']['matches'].clear()
    assert bulk.read('bulk-0')['trajectory']==steps[0], 'reading the complete audit never exports mutable private storage'

@pytest.mark.skip('Part 2')
def test_ordered_sqlite_observations(tmp_path):
    """Persist complete run snapshots and every ordered trajectory occurrence using supplied codecs."""
    path=tmp_path/'audit.sqlite';repository=AuditRepository(path);original=entry_fixture()
    repository.save(original);repository.close();repository=AuditRepository(path);restored=repository.load('run-001')
    assert restored==original, 'closing and reopening preserves the complete audit run exactly'
    assert restored['trajectory']==original['trajectory'] and len(restored['trajectory'])==4, 'trajectory occurrence slots retain repeated tools and nonmonotonic repeated timestamps'
    assert 'tool_output' not in restored['trajectory'][1] and restored['trajectory'][0]['tool_output'] is None, 'the supplied value codec preserves absent fields and observed null data'
    data=restored['output'][0]['data'];values=restored['trajectory'][2]['tool_output']['items']
    assert data['ratio'].hex()==(1/3).hex() and data['zero'].hex()==(-0.0).hex() and type(data['big']) is int and [type(value) for value in values]==[bool,int,float,float], 'the supplied value codec retains exact finite numeric types and signed zero'
    other=entry_fixture('run-002','coder');outside=entry_fixture('run-003','researcher','session-other')
    repository.save(other);repository.save(outside)
    assert [row['run_id'] for row in repository.for_session('session-001','researcher')]==['run-001'], 'session queries keep agent and session identities independent'
    short=deepcopy(original);short['trajectory']=original['trajectory'][1:2];short['status']='failed';short['error']={'type':'LookupError','message':'empty'}
    repository.save(short);repository.close();repository=AuditRepository(path)
    assert repository.load('run-001')==short and repository.load('run-002')==other, 'replacing one snapshot removes only its obsolete trajectory slots'
    restored=repository.load('run-001');restored['trajectory'].clear()
    assert repository.load('run-001')==short, 'loaded audit edits do not mutate the persisted observation slots'
    with pytest.raises(KeyError):repository.load('not-recorded')
    later=entry_fixture('run-004');repository.save(later)
    assert [row['run_id'] for row in repository.for_session('session-001','researcher')]==['run-001','run-004'], 'scoped audit histories retain each run in creation order'
    repository.close()

@pytest.mark.skip('Part 3')
def test_trust_modality_and_shared_projection(tmp_path):
    """Admit before effects, validate all tagged output modes and project one persisted observation."""
    repository=AuditRepository(tmp_path/'gateway.sqlite');store=AuditStore();effects=[];ids=count(1)
    cards={'researcher':{'output_modes':['text/plain','application/json','application/pdf']}}
    policy=PublicPolicy(tool_input=False,tool_output=True)
    gateway=ProtocolGateway(cards,lambda caller,agent:caller=='trusted',store,repository,count(100,7).__next__,lambda:f'gate-{next(ids)}',policy)
    parts=[{'kind':'text','text':'summary'},{'kind':'data','data':{'n':2},'media_type':'application/json'}, {'kind':'file','name':'local.pdf','url':'file:///not-read.pdf','media_type':'application/pdf'}]
    def handler(inputs,emit):
        effects.append(inputs['ticket']['id']);emit({'timestamp':105,'reasoning':'PRIVATE internal notes','tool_name':'lookup','tool_input':{'secret':'x'},'tool_output':{'found':True}})
        return {'invocation_id':len(effects),'parts':deepcopy(parts)}
    request={'ticket':{'id':'001'}}
    assert gateway.delegate('stranger','researcher',request,handler)=={'error':'untrusted caller'} and effects==[] and store.all()==[], 'untrusted admission causes no execution and no captured effect'
    success=gateway.delegate('trusted','researcher',request,handler,'same-session')
    assert success['task']['id']==success['audit']['run_id']=='gate-1' and success['task']['state']=='completed' and success['task']['parts']==parts and len(effects)==1, 'one accepted persisted observation supplies its task and public audit'
    assert success['audit']['trajectory']==[{'timestamp':105,'tool_name':'lookup','tool_output':{'found':True}}] and 'PRIVATE' not in json.dumps(success), 'the public audit exports only policy-selected structural tool observations'
    assert repository.load('gate-1')['trajectory'][0]['reasoning']=='PRIVATE internal notes', 'public redaction does not erase the private evidence'
    assert validate_declared_output(parts,cards['researcher']['output_modes']) and not validate_declared_output(parts,['text/plain','application/json']), 'every tagged file data or text modality must be declared'
    gateway.cards={'researcher':{'output_modes':['text/plain']}}
    rejected=gateway.delegate('trusted','researcher',request,handler,'same-session')
    assert rejected['task']['state']=='failed' and rejected['task']['parts']==[] and rejected['task']['error']['type']=='OutputModeError' and rejected['audit']['status']=='completed', 'undeclared observed output cannot become task success or falsify the actual execution outcome'
    assert rejected['task']['id']=='gate-2' and rejected['audit']['session_id']=='same-session' and len(effects)==2, 'a shared observational session does not collapse separate executions'
    def resolution_failure(caller,agent):raise ConnectionError('local trust fixture unavailable')
    gateway.trust=resolution_failure
    assert gateway.delegate('trusted','researcher',request,handler)=={'error':'untrusted caller'} and len(effects)==2, 'unavailable injected trust remains closed before any effect'
    gateway.trust=lambda caller,agent:True;gateway.cards=cards
    def failure(inputs,emit):raise LookupError('local task unavailable')
    failed=gateway.delegate('trusted','researcher',request,failure)
    assert failed['task']['state']=='failed' and failed['task']['error']=={'type':'LookupError','message':'local task unavailable'}, 'captured execution failure is projected without publishing an invented successful task'
    private=entry_fixture('public-owned');before_public=deepcopy(private)
    exported=project_task_and_public_audit(private,PublicPolicy(tool_input=True,tool_output=True))
    exported['audit']['trajectory'][0]['tool_input']['q']='edited'
    exported['audit']['trajectory'][2]['tool_output']['items'].append('edited')
    assert private==before_public, 'public tool snapshots do not mutate their captured source evidence'
    repository.close()

@pytest.mark.skip('Part 4')
def test_audit_domain_events_and_seal(tmp_path):
    """Accumulate observation slots and a coherent terminal audit through a supplied SSE driver."""
    entry=load_fixture(tmp_path/'stream.sqlite');policy=PublicPolicy(tool_input=True,tool_output=False)
    expected=[{'timestamp':step['timestamp'],**({'tool_name':step['tool_name']} if 'tool_name' in step else {}),**({'tool_input':step['tool_input']} if 'tool_input' in step else {})} for step in entry['trajectory']]
    async def exercise():
        state={'pulled':0,'closed':False}
        async def source():
            try:
                for step in entry['trajectory']:
                    state['pulled']+=1;yield {'kind':'step','run_id':entry['run_id'],'step':step}
                state['pulled']+=1;yield {'kind':'sealed','receipt':entry}
            finally:state['closed']=True
        output=stream_audit(source(),AuditProjection(entry['run_id'],policy));first=parse_sse(await output.__anext__())
        assert first==('audit-step',{'run_id':'run-001','slot':0,'observation':expected[0]}), 'the current audit patch retains its run and observation slot'
        assert state['pulled']==1, 'the supplied driver publishes the current audit observation before pulling another'
        await output.aclose()
        assert state=={'pulled':1,'closed':True}, 'the supplied driver closes a subscriber source without running a future observation'
        frames=[parse_sse(frame) async for frame in stream_audit(source(),AuditProjection(entry['run_id'],policy))]
        assert [data for name,data in frames[:-1]]==[{'run_id':'run-001','slot':slot,'observation':step} for slot,step in enumerate(expected)] and all(name=='audit-step' for name,data in frames[:-1]), 'every trajectory occurrence produces its own ordered structural audit patch'
        terminal=frames[-1]
        assert terminal==('audit-sealed',{'run_id':'run-001','agent':'researcher','session_id':'session-001','status':'completed','started_at':entry['started_at'],'completed_at':entry['completed_at'],'error':None,'trajectory_count':4}), 'the terminal audit follows all observed slots and retains the sealed run fields'
        assert 'reasoning' not in json.dumps(frames) and 'tool_output' not in json.dumps(frames), 'public stream payloads exclude private reasoning and unselected tool outputs'
    asyncio.run(exercise())
    failed=deepcopy(entry);failed['status']='failed';failed['error']={'type':'LookupError','message':'world 世界'}
    projection=AuditProjection(entry['run_id'],policy)
    for step in entry['trajectory']:projection.on_step(entry['run_id'],step)
    name,terminal=projection.on_seal(failed);projection.finish()
    assert name=='audit-sealed' and terminal['status']=='failed' and terminal['error']==failed['error'] and terminal['trajectory_count']==4, 'a failed terminal audit retains all prior observations and the original failure'
    with pytest.raises(ValueError,match='audit already sealed'):projection.on_step(entry['run_id'],entry['trajectory'][0])
    mismatch=AuditProjection(entry['run_id'],policy)
    with pytest.raises(ValueError,match='sealed trajectory differs'):mismatch.on_seal(entry)
    with pytest.raises(ValueError,match='without seal'):mismatch.finish()
    with pytest.raises(ValueError,match='audit run mismatch'):AuditProjection('different',policy).on_step(entry['run_id'],entry['trajectory'][0])
    zero=deepcopy(entry);zero['trajectory']=[]
    assert AuditProjection(entry['run_id'],policy).on_seal(zero)[1]['trajectory_count']==0, 'a zero-observation execution still has a real terminal receipt'
    coherent=AuditProjection(entry['run_id'],policy)
    for step in entry['trajectory']:coherent.on_step(entry['run_id'],step)
    different=deepcopy(entry);different['trajectory'][2]['tool_output']['items'].append('different')
    with pytest.raises(ValueError,match='sealed trajectory differs'):coherent.on_seal(different)

@pytest.mark.skip('Part 5')
def test_structural_did_relationships(tmp_path):
    """Resolve local DID relationship occurrences without treating structure as identity verification."""
    did='did:wba:local.test:agent:researcher'
    document={'id':did,'verificationMethod':[
        {'id':did+'#sign','controller':did,'type':'Ed25519VerificationKey2020','publicKeyDer':'opaque-public-one'},
        {'id':'#agree','controller':did,'type':'X25519KeyAgreementKey2019','publicKeyDer':'opaque-public-two'},
        {'id':did+'#foreign','controller':'did:wba:other.test:agent:x','type':'Ed25519VerificationKey2020','publicKeyDer':'opaque-public-three'}],
        'authentication':['#sign','#foreign','#missing'],
        'keyAgreement':[did+'#agree','#sign'],
        'humanAuthorization':['#sign','#agree','#sign'],
        'service':[{'id':'#description','serviceEndpoint':'https://not-fetched.invalid/agent.json'}]}
    before=deepcopy(document);rows=resolve_relationships(document)
    assert [(row['purpose'],row['reference']) for row in rows]==[(purpose,reference) for purpose in ('authentication','keyAgreement','humanAuthorization') for reference in document[purpose]], 'every relationship occurrence retains its purpose and original reference order'
    assert rows[0]['key_id']==did+'#sign' and rows[3]['key_id']==did+'#agree' and rows[3]['key']['id']=='#agree', 'relative fragments resolve within this DID while retaining the original key record'
    assert [row['findings'] for row in rows]==[[],['controller-mismatch'],['unresolved'],[],['purpose-mismatch'],[],['purpose-mismatch'],[]], 'signing agreement and human authorization remain distinct key purposes with explicit findings'
    assert rows[2]['key'] is None and rows[2]['key_id']==did+'#missing', 'unresolved relationship evidence remains visible without inventing a key'
    rows[0]['key']['publicKeyDer']='edited'
    assert document==before and rows[5]['key']['publicKeyDer']=='opaque-public-one', 'relationship records own their key snapshots without mutating the source document or another purpose'
    assert resolve_relationships({'id':did,'verificationMethod':[]})==[], 'a document without relationships has no invented authorization'
    repository=AuditRepository(tmp_path/'did.sqlite');entry=entry_fixture('did-run');entry['output']=[{'kind':'data','media_type':'application/json','data':document}];repository.save(entry)
    stored=repository.load('did-run');public=project_task_and_public_audit(stored,PublicPolicy())
    recovered=public['task']['parts'][0]['data']
    assert resolve_relationships(recovered)==resolve_relationships(document) and public['task']['id']==public['audit']['run_id']=='did-run', 'a persisted delegated document reaches the structural inspector through its one captured run'
    combined=deepcopy(document);combined['verificationMethod'][2]['type']='X25519KeyAgreementKey2019'
    assert resolve_relationships(combined)[1]['findings']==['controller-mismatch','purpose-mismatch'], 'independent DID inconsistencies remain visible on the same relationship'
    repository.close()
