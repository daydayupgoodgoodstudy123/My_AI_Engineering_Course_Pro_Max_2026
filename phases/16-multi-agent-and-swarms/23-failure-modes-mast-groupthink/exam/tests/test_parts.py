"""Five circuit, persistence, causal retry, event and nested amplification tasks."""
import asyncio,csv,io,json,re
from decimal import Decimal
from fractions import Fraction
from time import perf_counter
import pytest
from maststorm.models import Incident,IncidentRecord,Observation,CallNode,PhaseEvent
from maststorm.primitives import CircuitBreaker,categorize_incident,detect_groupthink
from maststorm.breaker_given import CircuitBreaker as GivenBreaker
from maststorm.service import detect_incident,detect_incident_given,BreakerDesk
from maststorm.fixture import breaker_fixture
from maststorm.store import IncidentArchive
from maststorm.csv_support import HEADER
from maststorm.cascade_support import CascadeIntake,ScriptedProvider,LogicalClock
from maststorm.cascade import invoke_attempt,execute_retry_tree,replay_cascade
from maststorm.sealed import replay_cascade as given_replay
from maststorm.wire_support import publish_incidents
from maststorm.stream import project_incidents
from maststorm.trace_support import TraceCatalog
from maststorm.structure import audit_amplification

def archived_record(path,budget=4):
    incident=Incident('incident-α','root/request','role_conflict',{'role_conflict':True,'style':True,'lineup':True,'note':'original,\n"symptom"'})
    detection=detect_incident_given(incident)
    record=IncidentRecord(detection.uid,detection.root,incident.primary,incident.symptoms,detection.category,detection.tags,'retry-action',budget,Observation('retry-action',9,None,'not independently cleared'))
    archive=IncidentArchive(path);archive.append(record);archive.close();archive=IncidentArchive(path);loaded=archive.reopen_records()[-1];archive.close();return loaded

def parsed_syslog(text):
    out=[]
    for line in text.splitlines():
        match=re.fullmatch(r'<(\d+)>1 (\S+) localhost maststorm - (\S+) \[incident ((?:\\.|[^\]])*)\] (.*)',line)
        if match is None:raise AssertionError('restricted syslog record syntax')
        attrs={k:re.sub(r'\\(.)',lambda m:m.group(1),v)for k,v in re.findall(r'(\w+)="((?:\\.|[^"\\])*)"',match[4])}
        out.append((int(match[1])-8,match[3],attrs,json.loads(match[5])))
    return tuple(out)

@pytest.mark.skip(reason='Part 1')
def test_part1_detection_breaker_and_complete_replay():
    """Retain original symptom evidence, single recovery probe and exact bounded rolling failure window."""
    incident=Incident('i','root','role_conflict',{'role_conflict':True,'style':True,'lineup':True})
    detection=detect_incident(incident)
    assert detection.category=='coord' and detection.primary_value is True and incident.symptoms['role_conflict'] is True, 'detection preserves the original primary symptom for the report consumer'
    assert detection.tags==('style','lineup') and detect_groupthink({'consensus':True})==('consensus',), 'all actual groupthink tags remain independently observable'
    unknown=detect_incident(Incident('u','root','new-symptom',{'new-symptom':'opaque'}));assert unknown.category=='unknown' and unknown.primary_value=='opaque', 'unknown category is a legitimate report, not a missing renderer branch'
    b=CircuitBreaker(2,.5,3);b.record(False,0);b.record(False,1)
    assert b.state=='OPEN' and not b.allow(2), 'a full above-threshold failure window opens until cooldown'
    assert b.allow(4) and b.state=='HALF_OPEN' and not b.allow(4) and not b.allow(5), 'only one half-open probe can own the recovery slot before its result'
    b.record(True,5);assert b.state=='CLOSED' and tuple(b.outcomes)==() and b.failures==0 and not b.probe_inflight, 'successful recovery clears the old failure window and probe ownership'
    b.record(False,6);assert b.state=='CLOSED' and b.failures==1 and len(b.outcomes)==1, 'old failures cannot immediately reopen a recovered breaker'
    c=CircuitBreaker(3,1,0);failures=[]
    for i,result in enumerate((False,False,True,True,True)):c.record(result,i);failures.append(c.failures)
    assert failures==[1,2,2,1,0] and tuple(c.outcomes)==(True,True,True), 'rolling failure count subtracts each actual expired outcome in FIFO order'
    d=CircuitBreaker(2,.5,0);d.record(False,0);d.record(True,1);assert d.state=='CLOSED' and d.failures==1, 'threshold equality stays closed under the declared strict comparison'
    other=CircuitBreaker(2,.5,0);assert tuple(other.outcomes)==() and other.failures==0 and other.state=='CLOSED', 'breaker windows and recovery ownership belong to each independent instance'
    failed_probe=CircuitBreaker(1,.5,2);failed_probe.record(False,0);admitted=failed_probe.allow(2);failed_probe.record(False,2)
    assert admitted and failed_probe.state=='OPEN' and failed_probe.opened_at==2 and not failed_probe.probe_inflight and not failed_probe.allow(3), 'an actual failed recovery probe reopens cooldown and releases its one probe slot'
    outcomes,window,expected=breaker_fixture();start=perf_counter();report=BreakerDesk().replay(outcomes,window)
    assert report==expected, 'every actual admission decision state sample and failure count plus the complete final window is retained'
    elapsed=perf_counter()-start
    assert elapsed<0.12, 'complete rolling-window replay stays within the declared local budget'

@pytest.mark.skip(reason='Part 2')
def test_part2_full_incident_csv_close_reopen(tmp_path):
    """Preserve original symptoms, every tag/action and independent validation in append order."""
    path=tmp_path/'incidents.csv';archive=IncidentArchive(path);huge=10**35+7
    r=IncidentRecord('id,α','request"one','role_conflict',{'role_conflict':True,'note':'quoted,\n"line"','n':huge,'threshold':Decimal('0.5000'),'flags':[False,None]},'coord',('style','lineup'),'fallback',huge,Observation('fallback',12,False,'symptom still present'))
    unknown=IncidentRecord('unknown','request-two','opaque',{'opaque':'not recognized'},'unknown',(),'try',0,Observation('try',13,None,'not measured'))
    cleared=IncidentRecord(r.uid,r.root,r.primary,r.symptoms,r.category,r.tags,r.action,2,Observation('fallback',14,True,'independent post-action clear'))
    for row in(r,unknown,cleared,r):archive.append(row)
    archive.close();archive=IncidentArchive(path);rows=archive.reopen_records();archive.close()
    assert rows==(r,unknown,cleared,r), 'quoted CSV reopen retains every complete original incident and independent observation in declared append order'
    assert rows[0].symptoms['threshold'].as_tuple()==r.symptoms['threshold'].as_tuple() and rows[0].call_budget==huge and type(rows[0].symptoms['flags'][0])is bool, 'the complete Given codec retains exact Decimal scale integer budget and ordinary typed data'
    assert tuple(x.validation.cleared for x in rows)==(False,None,True,False) and rows[1].category=='unknown', 'a diagnosis or mitigation attempt never replaces independent validation or legitimate unknown category'
    with path.open(newline='',encoding='utf-8')as f:raw=tuple(csv.reader(f))
    assert tuple(raw[0])==HEADER and len(raw)==5, 'all append records use the complete quoted CSV schema without deduplication or replacement'
    pointer=IncidentRecord('primary-pointer','root-primary','stale_context',{'style':True,'stale_context':True},'coord',('style',),'observe',3,Observation('observe',17,None,'separate original primary'))
    archive=IncidentArchive(tmp_path/'primary.csv');archive.append(pointer);archive.close();archive=IncidentArchive(tmp_path/'primary.csv');pointed=archive.reopen_records();archive.close()
    assert pointed==(pointer,), 'the declared primary symptom survives archive roundtrip independently of raw symptom insertion order'

@pytest.mark.skip(reason='Part 3')
def test_part3_shared_actual_budget_causal_retry_and_admission(tmp_path):
    """Share the root actual-call budget, retain successful effects, and keep non-invocations outcome-free."""
    record=archived_record(tmp_path/'cascade.csv',4)
    assert record.category=='coord' and record.tags==('style','lineup') and record.validation.cleared is None, 'cascade actually consumes repaired detection through closed and reopened incident CSV'
    a=CallNode('a','A');b=CallNode('b','B');parent=CallNode('parent','A',(a,b),2);tail=CallNode('tail','B')
    provider=ScriptedProvider({'a':(True,),'b':(False,True),'parent':(True,),'tail':(True,)})
    context=CascadeIntake(record,(parent,tail),provider);report=replay_cascade(context)
    assert report.root==record.root and report.incident==record.uid and report.used==4 and report.remaining==0 and len(report.nodes)==2 and report.nodes[1].status=='failed', 'all nested services and later roots share the original incident actual-call budget'
    assert report.calls==(('a','A',True),('b','B',False),('b','B',True),('parent','A',True)) and report.effects==('a','b','parent'), 'retrying a failed dependency preserves successful effects by effect UID rather than service name'
    first,second=report.nodes[0].tries
    assert first.invocation.status=='dependency-failed' and not first.invocation.actual and second.children[0].status=='cached' and second.invocation.success is True, 'causal dependencies settle before the parent and successful siblings do not execute again'
    blocked=report.nodes[1].tries[0].invocation
    assert blocked.status=='budget-exhausted' and not blocked.actual and blocked.success is None and 'tail'not in provider.counts, 'exhausted root budget produces no new provider call or fabricated downstream outcome'
    probe=GivenBreaker(1,.5,3);p=ScriptedProvider({'retry':(False,True)});node=CallNode('retry','S',attempts=4);context=CascadeIntake(record,(node,),p,{'S':probe});short=replay_cascade(context)
    assert tuple(t.invocation.status for t in short.nodes[0].tries)==('invoked','short-circuit','short-circuit','invoked') and short.calls==(('retry','S',False),('retry','S',True)) and short.used==2, 'breaker short-circuit is outcome-free and consumes no actual provider budget before a later true recovery probe'
    zero=archived_record(tmp_path/'zero.csv',0);probe=GivenBreaker(1,.5,0);probe.state='OPEN';p=ScriptedProvider({'z':(True,)});context=CascadeIntake(zero,(CallNode('z','S'),),p,{'S':probe},LogicalClock(5));z=replay_cascade(context)
    assert z.used==0 and z.calls==() and probe.state=='OPEN' and not probe.probe_inflight, 'budget admission happens before breaker allow so zero calls cannot reserve a half-open probe'
    five=archived_record(tmp_path/'five-attempts.csv',5);node=CallNode('fifth','R',attempts=5);p=ScriptedProvider({'fifth':(False,False,False,False,True)})
    context=CascadeIntake(five,(node,),p);five_report=replay_cascade(context)
    assert five_report.used==5 and five_report.nodes[0].status=='success' and len(five_report.nodes[0].tries)==5 and five_report.calls==(('fifth','R',False),)*4+(('fifth','R',True),), 'the configured positive attempt bound permits a successful fifth actual invocation'
    first=CallNode('first-fails','F');later=CallNode('later-independent','H');parent=CallNode('blocked-parent','P',(first,later));p=ScriptedProvider({'first-fails':(False,),'later-independent':(True,),'blocked-parent':(True,)})
    context=CascadeIntake(record,(parent,),p);siblings=replay_cascade(context)
    assert siblings.calls==(('first-fails','F',False),('later-independent','H',True)) and siblings.used==2 and tuple(c.status for c in siblings.nodes[0].tries[0].children)==('failed','success') and siblings.nodes[0].tries[0].invocation.status=='dependency-failed', 'a failed dependency blocks its parent while every later independent sibling is still considered in declared order'

@pytest.mark.skip(reason='Part 4')
def test_part4_actual_phase_correlation_and_syslog(tmp_path):
    """Project each incident event and its own independent post-action observation through the supplied wire driver."""
    original=archived_record(tmp_path/'events.csv',4);r=IncidentRecord('id]"\\α',original.root,original.primary,original.symptoms,'unknown',original.tags,'fallback]"\\',4,original.validation)
    events=(PhaseEvent('e0',r,'detected'),PhaseEvent('e1',r,'diagnosed'),PhaseEvent('e2',r,'validated',Observation(r.action,2,False,'fallback ran, symptom remains')),PhaseEvent('e3',r,'validated',Observation(r.action,3,None,'not observed')),PhaseEvent('e4',r,'validated',Observation(r.action,4,True,'actually clear,\nquoted "ok"')))
    peer=IncidentRecord('peer','other/root',r.primary,r.symptoms,'coord',(),'other-action',2,r.validation);events=events+(PhaseEvent('e5',peer,'detected'),)
    rows=parsed_syslog(asyncio.run(publish_incidents(events,project_incidents)))
    assert len(rows)==6 and tuple(x[1]for x in rows)==tuple(e.uid for e in events), 'every actual event publishes its own syslog event identity exactly once'
    assert all(x[2]['uid']==r.uid and x[2]['root']==r.root and x[2]['category']=='unknown' and x[2]['action']==r.action for x in rows[:5]), 'restricted structured data retains each incident correlation category and actual action with escaping'
    assert tuple(x[2]['phase']for x in rows)==('detected','diagnosed','validated','validated','validated','detected') and tuple(x[0]for x in rows)==(3,4,3,4,5,3), 'severity follows the complete actual phase and observation classifier, not optimistic fallback text'
    assert tuple(x[2]['closing']for x in rows)==('false','false','false','false','true','false'), 'only actual post-action positive validation can close an incident, never diagnosis fallback or unknown observation'
    assert rows[-1][2]['uid']=='peer' and rows[-1][2]['root']=='other/root' and rows[-1][2]['category']=='coord' and rows[-1][2]['action']=='other-action', 'each different incident keeps its own event correlation and diagnosis fields'
    assert tuple(x[3]for x in rows)==('','','fallback ran, symptom remains','not observed','actually clear,\nquoted "ok"',''), 'each validated event retains its own actual observation note including quoted newlines'

@pytest.mark.skip(reason='Part 5')
def test_part5_nested_attempt_edges_and_amplification(tmp_path):
    """Fold actual calls and pruning at every sealed retry edge without reimplementing breaker or budget admission."""
    record=archived_record(tmp_path/'nested.csv',4);a=CallNode('a','A');b=CallNode('b','B');parent=CallNode('parent','A',(a,b),2);tail=CallNode('tail','B');p=ScriptedProvider({'a':(True,),'b':(False,True),'parent':(True,),'tail':(True,)})
    context=CascadeIntake(record,(parent,tail),p);sealed=given_replay(context);audit=audit_amplification(TraceCatalog(context,sealed));main,last=audit.roots
    assert audit.root==record.root and audit.incident==record.uid and audit.actual_calls==len(sealed.calls)==4 and audit.amplification==Fraction(2), 'nested accounting actually consumes detection CSV reopen and complete Given P3 execution for the originating request'
    assert audit.distinct_services==('A','B') and main.own_calls==1 and main.total_calls==4, 'actual invocation count is not the number of distinct service names'
    assert tuple((e.attempt,e.child,e.audit.own_calls,e.audit.total_calls)for e in main.edges)==((1,'a',1,1),(1,'b',1,1),(2,'a',0,0),(2,'b',1,1)), 'each retry retains its actual child edge and cached success contributes zero new calls'
    assert tuple(x[:4]for x in main.attempts)==((1,'dependency-failed',False,None),(2,'invoked',True,True)) and main.status=='success', 'parent dependency-failure and actual provider success remain separate ordinal evidence'
    assert last.own_calls==0 and last.total_budget_blocks==1 and audit.budget_blocks==((('tail',1),),), 'a blocked later root contributes zero actual calls with its own complete request path'
    node=CallNode('outer','C',(CallNode('leaf','S',attempts=2),),2);p=ScriptedProvider({'leaf':(False,),'outer':(True,)});context=CascadeIntake(record,(node,),p,{'C':GivenBreaker(2,1,5),'S':GivenBreaker(1,.5,20)});sealed=given_replay(context);pruned=audit_amplification(TraceCatalog(context,sealed))
    assert pruned.actual_calls==1 and pruned.roots[0].own_calls==0 and pruned.roots[0].total_shortcircuits==3 and len(pruned.shortcircuits)==3, 'every short-circuited child occurrence is explained without inventing provider success or load'
    deep=CallNode('top','A',(CallNode('middle','B',(CallNode('bottom','A'),)),));p=ScriptedProvider({'top':(True,),'middle':(True,),'bottom':(True,)});context=CascadeIntake(record,(deep,),p);deep_report=given_replay(context);deep_audit=audit_amplification(TraceCatalog(context,deep_report));top=deep_audit.roots[0]
    assert deep_audit.actual_calls==3 and top.total_calls==3 and top.edges[0].audit.total_calls==2 and top.edges[0].audit.edges[0].audit.total_calls==1 and top.edges[0].audit.edges[0].child=='bottom', 'recursive audit retains every actual level through repeated service names A B A rather than a flat immediate-child summary'
    empty=CascadeIntake(record,(),ScriptedProvider({}));empty_report=given_replay(empty);empty_audit=audit_amplification(TraceCatalog(empty,empty_report))
    assert empty_audit.actual_calls==0 and empty_audit.roots==() and empty_audit.amplification==0, 'an empty finite request forest has no actual load or artificial amplification'
    assert pruned.shortcircuits==((('outer',1),('leaf',2)),(('outer',2),('leaf',1)),(('outer',2),('leaf',2))), 'each nested pruning occurrence retains all ancestor node and retry ordinals'
    order_root=CallNode('order-parent','A',(CallNode('order-child','Z'),));p=ScriptedProvider({'order-parent':(True,),'order-child':(True,)})
    context=CascadeIntake(record,(order_root,),p);ordered_report=given_replay(context);ordered_audit=audit_amplification(TraceCatalog(context,ordered_report))
    assert ordered_audit.distinct_services==('Z','A') and ordered_report.calls==(('order-child','Z',True),('order-parent','A',True)), 'distinct services follow their first actual dependency-first invocation order independently of their names'
