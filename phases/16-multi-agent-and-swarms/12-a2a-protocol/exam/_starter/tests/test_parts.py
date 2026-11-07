"""Five locked parts: task polling; attempt archives; card/review adaptation;
change-only SSE observations; nested file/group review-domain reports.
"""
import asyncio
from dataclasses import replace
import json
import time
import pytest
from peerresult.models import Artifact,TaskEnvelope,PollRequest,BatchResult,Attempt,ReviewResult,FileReport,Issue,ReviewGroup,ReviewBundle,Finding
from peerresult.transport import LocalTransport,envelope_status
from peerresult.primitives import make_poll_url,task_id_from_route,classify_terminal
from peerresult.service import PollDesk
from peerresult.fixture import PEER,wire,polling_fixture,local_card
from peerresult.store import AttemptArchive
from peerresult.adapter import validate_local_card,negotiate_review_modality,adapt_review
from peerresult.stream import TaskProjection
from peerresult.wire_support import publish_sse
from peerresult.review import audit_review

@pytest.mark.skip('Part 1')
def test_discovered_terminal_polling_and_pending_lifecycle():
    """Repair discovery routing, terminal receipts and complete pending-only business polling."""
    transport=LocalTransport({PEER:{'remote-only':((0,wire('remote-only','completed',Artifact('text','done'))),)}})
    polled=transport.get(make_poll_url(PEER,'remote-only'),0,task_id_from_route)
    assert polled['id']=='remote-only','poll requests reach the discovered peer'
    routed=transport.get(make_poll_url(PEER,'remote-only','trace=1'),0,task_id_from_route)
    assert routed==polled,'query parameters do not change task identity'
    failed=classify_terminal(wire('failed','failed',Artifact('text','unknown skill')),4)
    assert envelope_status(failed)=='error' and failed==TaskEnvelope('failed','failed',Artifact('text','unknown skill'),4),'HTTP success does not turn a failed task into a result'
    requests,transport,expected=polling_fixture()
    started=time.perf_counter()
    result=PollDesk(transport).run(requests)
    assert result==expected,'complete polling retains every task artifact terminal state and first observation'
    elapsed=time.perf_counter()-started
    assert elapsed<0.07,'completed tasks do not delay the remaining real task observations'
    edge_requests=(PollRequest('on-time',PEER,2),PollRequest('too-late',PEER,1),PollRequest('failed',PEER,0))
    transport=LocalTransport({PEER:{'on-time':((0,wire('on-time','working')),(2,wire('on-time','completed',Artifact('structured',{'issues':[],'lines':0})))),'too-late':((0,wire('too-late','working')),(2,wire('too-late','completed',Artifact('text','late')))),'failed':((0,wire('failed','failed',Artifact('text','denied'))),)}})
    assert PollDesk(transport).run(edge_requests)==BatchResult((TaskEnvelope('on-time','completed',Artifact('structured',{'issues':[],'lines':0}),2),TaskEnvelope('too-late','timeout',None,1),TaskEnvelope('failed','failed',Artifact('text','denied'),0))),'each task keeps its own deadline and every terminal outcome'
    assert PollDesk(LocalTransport({})).run(())==BatchResult(()),'an empty batch has no invented task observations'
    assert classify_terminal(wire('working','working'),0)is None,'working observations remain unfinished'

@pytest.mark.skip('Part 2')
def test_ordered_attempt_manifest_and_exact_artifacts(tmp_path):
    """Persist all attempt metadata and its exact independently stored artifact association."""
    text='{"issues": ["保留原文"], "lines": 7}\n'
    structured={'issues':['α','α'],'lines':7,'extension':{'token':2**60+17,'empty':[],'nothing':None,'score':1.0000000000000002}}
    first=Attempt('task-z',2,PEER,'0.1.0',TaskEnvelope('task-z','failed',Artifact('text',text),3))
    second=Attempt('task-z',3,'http://backup.local/tasks','0.2.0',TaskEnvelope('task-z','completed',Artifact('structured',structured),9))
    third=Attempt('task-a',0,PEER,'0.1.0',TaskEnvelope('task-a','timeout',None,12))
    attempts=(first,second,third);path=tmp_path/'attempts'
    AttemptArchive(path).save(attempts)
    assert AttemptArchive(path).load()==attempts,'reopening retains every ordered task attempt and its own exact artifact'
    manifest=json.loads((path/'manifest.json').read_text())
    assert [(e['task_id'],e['attempt'],e['state'],e['peer'])for e in manifest]==[('task-z',2,'failed',PEER),('task-z',3,'completed','http://backup.local/tasks'),('task-a',0,'timeout',PEER)],'manifest records retain complete attempt association and declared order'
    assert [e['tag']for e in manifest]==['text','structured',None] and manifest[0]['member']!=manifest[1]['member'] and manifest[2]['member']is None,'each artifact member belongs to its own declared attempt'
    assert (path/manifest[0]['member']).read_bytes()==text.encode('utf-8'),'the supplied tagged codec preserves exact opaque text bytes'
    updated=(replace(second,envelope=replace(second.envelope,observed_at=11)),first)
    AttemptArchive(path).save(updated)
    assert AttemptArchive(path).load()==updated,'a replacement snapshot follows its new complete attempt sequence'
    other=tmp_path/'other';AttemptArchive(other).save((third,));AttemptArchive(path).save(())
    assert AttemptArchive(path).load()==() and AttemptArchive(other).load()==(third,),'separate archive snapshots retain their own declared membership'

@pytest.mark.skip('Part 3')
def test_pinned_card_mode_and_flat_review_adapter(tmp_path):
    """Implement local card pinning, advertised-tag negotiation and flat review-domain validation."""
    card=local_card();assert validate_local_card(card)==card,'the pinned lesson-local card remains usable'
    for changed in ({'protocol_version':'1.0'},{'protocol_version':'a2a-0.30'},{'skills':'review-python'},{'endpoints':{'task_url':PEER}},{'auth':{'type':'bearer'}},{'modalities':['application/json']}):
        with pytest.raises(ValueError):validate_local_card({**card,**changed})
    artifact=Artifact('structured',{'issues':['missing return','missing return'],'lines':0})
    assert negotiate_review_modality(card,artifact)=='structured','advertised modality is checked against the explicit artifact tag'
    with pytest.raises(ValueError):negotiate_review_modality(local_card(('text',)),artifact)
    assert adapt_review(card,TaskEnvelope('review','completed',artifact,1))==ReviewResult('review','structured',('missing return','missing return'),0),'structured review preserves issue order and declared zero-line count'
    opaque='{"issues": [], "lines": 99}'
    assert adapt_review(card,TaskEnvelope('text','completed',Artifact('text',opaque),0))==ReviewResult('text','text',text=opaque),'JSON-looking text remains an explicit opaque text review'
    for bad in ({'issues':('tuple',),'lines':4},{'issues':[7],'lines':4},{'issues':[],'lines':True},{'issues':[],'lines':-1},{'issues':[],'lines':4.0},{'issues':[],'lines':4,'nested':{}}):
        with pytest.raises(ValueError):adapt_review(card,TaskEnvelope('bad','completed',Artifact('structured',bad),0))
    with pytest.raises(ValueError):adapt_review(card,TaskEnvelope('bad','failed',Artifact('text','unknown skill'),0))
    assert adapt_review(card,TaskEnvelope('large','completed',Artifact('structured',{'issues':[],'lines':2**54+1}),0)).lines==2**54+1,'declared integer review line counts remain exact'
    polled=PollDesk(LocalTransport({PEER:{'archived-review':((0,wire('archived-review','working')),(1,wire('archived-review','completed',Artifact('structured',{'issues':['retained finding'],'lines':2}))))}})).run((PollRequest('archived-review',PEER,3),)).results[0]
    archive=AttemptArchive(tmp_path/'adapter-evidence');archive.save((Attempt('archived-review',1,PEER,card['version'],polled),))
    reopened=AttemptArchive(tmp_path/'adapter-evidence').load()[0]
    assert adapt_review(card,reopened.envelope)==ReviewResult('archived-review','structured',('retained finding',),2),'the review adapter consumes the real polled and reopened attempt artifact'

    extended_card={**card,'documentation':{'note':'local extension'}}
    assert validate_local_card(extended_card)==extended_card,'local card extension fields remain permitted'
    for missing_fields in ({'issues':[]},{'lines':0},{}):
        with pytest.raises(ValueError,match='flat review shape'):
            adapt_review(card,TaskEnvelope('incomplete','completed',Artifact('structured',missing_fields),0))

@pytest.mark.skip('Part 4')
def test_change_only_local_task_sse():
    """Project observed task changes in domain order through the complete supplied SSE driver."""
    snapshots=[wire('sse','submitted'),wire('sse','submitted'),wire('sse','working'),wire('sse','working',Artifact('structured',{'issues':['x'],'lines':2})),wire('sse','working',Artifact('structured',{'issues':['x'],'lines':2})),wire('sse','working',Artifact('structured',{'issues':['y'],'lines':2})),wire('sse','failed',Artifact('text','{"error":"不是结果"}'))]
    class Source:
        def __init__(self):self.index=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index>=len(snapshots):raise AssertionError('a terminal snapshot ends observation')
            item=snapshots[self.index];self.index+=1;return item
        async def aclose(self):self.closed=True
    async def collect():
        source=Source();frames=[frame async for frame in publish_sse(source,TaskProjection())];return source,frames
    source,frames=asyncio.run(collect());events=[]
    for frame in frames:
        assert frame.endswith(b'\n\n'),'the supplied SSE codec publishes complete local event frames'
        lines=frame.decode('utf-8').rstrip('\n').split('\n');events.append((lines[0][7:],json.loads(lines[1][6:])))
    assert [event for event,data in events]==['local-state','local-state','local-artifact','local-artifact','local-state','local-artifact','local-final'],'only actual changes produce ordered state artifact and final events'
    assert events[2][1]=={'task_id':'sse','artifact':{'type':'structured','data':{'issues':['x'],'lines':2}}} and events[3][1]['artifact']['data']['issues']==['y'],'artifact changes are observed independently of task state changes'
    assert events[-1]==('local-final',{'task_id':'sse','state':'failed','artifact':{'type':'text','data':'{"error":"不是结果"}'}}),'the supplied terminal view preserves the failed task and its opaque error artifact'
    assert source.index==len(snapshots) and source.closed,'the supplied driver closes the source at its terminal observation'
    projection=TaskProjection();projection.events(snapshots[-1])
    assert projection.events(snapshots[-1])==(),'a projection emits its final event only once'

    clearing=TaskProjection()
    clearing.events(wire('clear','working',Artifact('structured',{'issues':[],'lines':2})))
    assert clearing.events(wire('clear','working'))==(('local-artifact',{'task_id':'clear','artifact':None}),),'an observed artifact removal is a task artifact change'
    assert clearing.events(wire('clear','working'))==(),'a repeated absent artifact does not create another change'

@pytest.mark.skip('Part 5')
def test_nested_review_file_lines_and_group_reports(tmp_path):
    """Build hierarchical file/span reports using fully supplied identity and occurrence expansion."""
    shared=Issue('shared','a.py',3,3,'reused issue');outside=Issue('outside','a.py',4,7,'escapes own group');wrong_file=Issue('other','b.py',3,3,'another file');bad_lines=Issue('bad-lines','a.py',0,2,'invalid span')
    deep=ReviewGroup('deep','a.py',4,5,('outside',))
    unknown=ReviewGroup('unknown','a.py',1,3,(),schema='future-group')
    missing=ReviewGroup('missing','missing.py',1,2)
    child=ReviewGroup('child','a.py',2,8,('shared','other','bad-lines'),(deep,unknown,missing))
    root=ReviewGroup('root','a.py',1,12,('shared',),(child,))
    bundle=ReviewBundle((FileReport('a.py',12),FileReport('b.py',5)),(shared,outside,wrong_file,bad_lines),(root,))
    audit=audit_review(Artifact('structured',bundle))
    expected=(Finding(('artifact','root','child','other'),'issue-file'),Finding(('artifact','root','child','bad-lines'),'issue-lines'),Finding(('artifact','root','child','bad-lines'),'group-membership'),Finding(('artifact','root','child','deep','outside'),'group-membership'),Finding(('artifact','root','child','unknown'),'schema'),Finding(('artifact','root','child','unknown'),'child-span'),Finding(('artifact','root','child','missing'),'group-file'),Finding(('artifact','root','child','missing'),'child-span'))
    assert audit.findings==expected,'nested review findings retain exact file line group and schema locations'
    assert audit.groups[0].group_id=='root' and audit.groups[0].findings==() and audit.groups[0].children[0].group_id=='child' and len(audit.groups[0].children[0].children)==3,'domain reports retain each own group and its declared nested children'
    assert audit.groups[0].children[0].children[0].findings==(Finding(('artifact','root','child','deep','outside'),'group-membership'),),'a nested issue is checked against its own group span'
    assert audit.unique_issues==4 and audit.memberships==5,'the supplied catalog retains canonical identities and all shared memberships'
    valid=ReviewBundle((FileReport('a.py',12),),(shared,),(ReviewGroup('outer','a.py',1,12,('shared',),(ReviewGroup('inner','a.py',3,3,('shared',)),)),))
    valid_audit=audit_review(Artifact('structured',valid))
    assert valid_audit.findings==() and valid_audit.unique_issues==1 and valid_audit.memberships==2,'the supplied expansion preserves valid shared membership without invented findings'
    text='{"schema":"review-tree-v1","issues":[]}'
    assert audit_review(Artifact('text',text)).text==text,'the supplied leaf dispatcher keeps text review content opaque'
    unknown_root=replace(valid,schema='unknown-tree')
    assert audit_review(Artifact('structured',unknown_root)).findings==(Finding(('artifact',),'schema'),),'an unknown local review schema reports its full artifact location'
    boundary=ReviewBundle((FileReport('a.py',12),),(Issue('last','a.py',12,12,'last line'),),(ReviewGroup('edge','a.py',12,12,('last',)),))
    assert audit_review(Artifact('structured',boundary)).findings==(),'declared final file and group line boundaries remain inclusive'
    unused=replace(valid,issues=valid.issues+(Issue('unreferenced','a.py',11,11,'catalog only'),))
    assert audit_review(Artifact('structured',unused)).unique_issues==2 and audit_review(Artifact('structured',unused)).memberships==2,'the supplied catalog counts all declared canonical issues independently of memberships'
    envelope=PollDesk(LocalTransport({PEER:{'nested-text':((0,wire('nested-text','completed',Artifact('text',text))),)}})).run((PollRequest('nested-text',PEER,1),)).results[0]
    archive=AttemptArchive(tmp_path/'nested-evidence');archive.save((Attempt('nested-text',0,PEER,'0.1.0',envelope),))
    reopened=AttemptArchive(tmp_path/'nested-evidence').load()[0].envelope;flat=adapt_review(local_card(),reopened)
    assert audit_review(reopened.artifact).text==flat.text==text,'nested leaf auditing consumes the real polled archived and flat-adapted text evidence'

    physical=ReviewBundle((FileReport('owner.py',10),FileReport('issue.py',5)),(Issue('physical','issue.py',4,7,'beyond declared issue file'),),(ReviewGroup('physical-group','owner.py',1,10,('physical',)),))
    assert audit_review(Artifact('structured',physical)).findings==(Finding(('artifact','physical-group','physical'),'issue-file'),Finding(('artifact','physical-group','physical'),'issue-lines')),'each issue physical interval uses its own declared file'
