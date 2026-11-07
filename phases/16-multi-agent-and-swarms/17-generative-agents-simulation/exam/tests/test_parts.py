"""Five locked stages: real inspection, per-agent continuation, reflection/revision, calendar evidence and nested physical execution."""
import json,time,math
from decimal import Decimal
from dataclasses import replace
import pytest
from smallvillelab.models import *
from smallvillelab.primitives import invitation_recipients,eligible_observation,pending_importance_since,prepare_query
from smallvillelab.service import TownDesk
from smallvillelab.store import TownArchive
from smallvillelab.reasoning import rank_memories,reflect_from_sources,revise_affected_plan
from smallvillelab.stream import calendar_fields
from smallvillelab.calendar_support import CalendarCatalog,calendar_observations,publish_calendar,parse_calendar
from smallvillelab.structure_support import World,PlanCatalog
from smallvillelab.structure import execute_nested_plan
from smallvillelab.fixture import inspection_fixture

def population():
    plans=(Segment('meeting',0,10,20,'park','old meeting'),Segment('work',3,20,30,'library','work unchanged'),Segment('unresolved',0,12,18,'park','unresolved'))
    memories=(Memory('raw-cause',0,8,'observation','cafe is open',8,(),('meeting','unresolved')),Memory('future',1,12,'observation','future party',9),Memory('done',2,9,'observation','already consumed',10),Memory('recent-low',3,10,'observation','cafe recent',1),Memory('prior-reflection',4,9,'reflection','cafe inference',6,('done',)))
    a=AgentState('a','Alice','home',memories,Progress(('done',),9),(),plans)
    b=AgentState('b','Bob','park',(),Progress(),(),(Segment('bob-meeting',0,10,20,'cafe','Bob visit'),))
    return a,b

def replayed(tmp_path):
    a,b=population();inspection=TownDesk().inspect(InspectionRequest((a,b),'a','Come to cafe',10,5,'cafe',8))
    snapshot=TownSnapshot('sim',10,Decimal('0'),tuple(x.state for x in inspection.agents));archive=TownArchive(tmp_path);archive.save(snapshot);archive.close();archive=TownArchive(tmp_path);restored=archive.load();archive.close()
    proposal=ReflectionProposal('new-reflection',20,'move the meeting',('raw-cause','done','prior-reflection','missing','future'))
    reflection=reflect_from_sources(restored.agents[0],proposal,10,5,8)
    patches=(PlanPatch('meeting',10,20,'cafe','Meet; cafe,\nSIMULATED'),PlanPatch('work',0,1,'park','irrelevant replacement'))
    revision=revise_affected_plan(reflection,patches)
    return inspection,restored,reflection,revision

def venues():
    return (Venue('home','Home',10,((0,100),)),Venue('park','Park',5,((0,100),)),Venue('cafe','Cafe; east,\nRoom',1,((10,21),)),Venue('library','Library',1,((0,100),)))

@pytest.mark.skip('Part 1')
def test_population_available_pending_and_complete_query_inspection():
    """Inspect actual declared recipients, nonfuture windows, independent consumed progress and every real memory relevance feature within the complete response budget."""
    a,b=population();request=InspectionRequest((a,b),'a','Come to cafe',10,5,'cafe',8);actual=TownDesk().inspect(request)
    assert actual.delivered_to==('b',) and actual.agents[1].state.memories[-1].content=='Come to cafe' and actual.agents[0].state==a,'invitations reach the actual other declared agents without changing the sender'
    assert tuple(x.memory.uid for x in actual.agents[0].features)==('raw-cause','done','recent-low','prior-reflection'),'available memory evidence excludes future observations and retains every currently eligible kind'
    assert actual.agents[0].pending_importance==9 and actual.agents[0].reflection_due and actual.agents[1].pending_importance==8,'reflection gates use only unconsumed raw observation importance rather than prior belief text'
    query,expected=inspection_fixture();started=time.perf_counter();observed=TownDesk().inspect(query)
    assert observed==expected,'the complete population delivery request every memory feature independent progress and due report remain exact'
    elapsed=time.perf_counter()-started
    assert elapsed<0.035,'complete supplied town inspection respects the local response budget'
    assert prepare_query('CAFE missing')('cafeteria')==0.6 and prepare_query('absent CAFE')('CAFE')==0.6 and prepare_query('')('anything')==0.1 and prepare_query('unrelated')('cafe')==0.1,'query features retain case-insensitive any-substring tail-match empty-query and no-match behavior'
    assert eligible_observation(Memory('edge',0,5,'observation','x',1),10,5) and not eligible_observation(Memory('old',0,4,'observation','x',1),10,5),'the declared memory window includes its exact old endpoint and excludes earlier evidence'
    future=(Memory('later-low-seq',1,12,'observation','later',9),Memory('now-high-seq',2,10,'observation','now',8));progress=Progress(('now-high-seq',),10)
    assert pending_importance_since(future,progress,12,5)==9 and pending_importance_since(future,progress,10,5)==0,'an unavailable lower-sequence observation remains pending when its actual time arrives'
    third=replace(b,uid='c',memories=());changed=TownDesk().inspect(replace(request,population=(a,b,third),sender_uid='b',now=11,query='unrelated'))
    assert changed.delivered_to==('a','c') and tuple(x.memory.uid for x in changed.agents[1].features)==tuple(m.uid for m in b.memories) and all(f.relevance==0.1 for x in changed.agents for f in x.features),'changed populations sender time and query retain their actual independent inspection evidence'

@pytest.mark.skip('Part 2')
def test_independent_agent_memory_progress_belief_and_plan_directory(tmp_path):
    """Reopen each complete per-agent state and manifest order, preserving explicit independent progress and all ordered linked memory/plan fields."""
    a,b=population();a=replace(a,name='同名',progress=Progress(('done','raw-cause'),0));b=replace(b,name='同名',memories=(Memory('b-memory',2**60+1,0,'observation','repeat text',7,('external',),('bob-meeting',)),Memory('b-memory2',2**60+2,0,'observation','repeat text',8)),beliefs=(Belief('belief-b','complete belief',('b-memory',)),))
    snapshot=TownSnapshot('town',2**60+7,Decimal('123456789.000000000000000001'),(b,a));archive=TownArchive(tmp_path);archive.save(snapshot);archive.close();archive=TownArchive(tmp_path);actual=archive.load();archive.close()
    assert actual==snapshot,'each declared agent reopens its own complete exact memory progress beliefs plans and town metadata'
    assert tuple(x.uid for x in actual.agents)==('b','a') and actual.agents[0].name==actual.agents[1].name,'manifest order and stable agent identity remain independent of display names'
    assert actual.agents[1].progress==Progress(('done','raw-cause'),0) and actual.agents[1].beliefs==(),'explicit consumed progress survives an empty belief collection and a zero reflection tick'
    assert actual.agents[0].memories[0].source_ids==('external',) and actual.agents[0].memories[0].contradicts==('bob-meeting',) and len(actual.agents[0].memories)==2,'ordered repeated memory text retains each own identity source and contradiction links'
    assert actual.agents[1].plans[1]==a.plans[1] and actual.wall_origin==snapshot.wall_origin,'complete plan interval revision venue note status and exact wall origin survive the supplied scalar codec'
    replacement=replace(snapshot,now=0,agents=(replace(a,location='library',memories=(),progress=Progress()),));archive=TownArchive(tmp_path);archive.save(replacement);archive.close();archive=TownArchive(tmp_path)
    assert archive.load()==replacement,'saving a complete town replacement does not resurrect stale members from an earlier directory snapshot'
    archive.close()

@pytest.mark.skip('Part 3')
def test_composite_rank_grounded_reflection_and_only_affected_plan_revision(tmp_path):
    """Compute stable composite retrieval, consume only actual grounded reflection sources, and revise only affected plan segments after real inspection/archive reopening."""
    inspection,restored,reflection,revision=replayed(tmp_path);a=restored.agents[0]
    ranked=rank_memories(a,10,5,'cafe',3)
    expected=sorted([(m.uid,math.exp(-0.3*(10-m.tick))+m.importance/10+(0.6 if 'cafe'in m.content.lower()else 0.1))for m in a.memories if 0<=10-m.tick<=5],key=lambda x:-x[1])[:3]
    assert tuple((x.uid,x.score)for x in ranked)==tuple(expected),'ranking combines actual recency importance and lexical relevance over the reopened available memories'
    low=replace(a,memories=(Memory('old-high',0,5,'observation','other',10),Memory('low-now',1,10,'observation','cafe',1),Memory('low-tie',2,10,'observation','cafe',1)))
    assert tuple(x.uid for x in rank_memories(low,10,5,'cafe',3))==('low-now','low-tie','old-high'),'low-importance relevant recent memories remain eligible and equal scores retain declaration order'
    assert reflection.used_source_ids==('raw-cause',) and reflection.rejected_source_ids==('done','prior-reflection','missing','future'),'a reflection cites only its actual eligible unconsumed raw observations rather than fabricated future or self-feedback sources'
    assert reflection.state.memories[-1].source_ids==('raw-cause',) and reflection.state.beliefs[-1].source_ids==('raw-cause',) and reflection.state.progress==Progress(('done','raw-cause'),10),'reflection memory belief and explicit progress agree on exactly the sources actually consumed'
    assert 'recent-low'not in reflection.state.progress.consumed_source_ids and reflection.state.memories[-1].kind=='reflection','uncited pending observations remain available for a later reflection and derived beliefs are typed separately'
    again=reflect_from_sources(reflection.state,ReflectionProposal('again',21,'again',('raw-cause',)),10,5,8)
    assert again.state==reflection.state and again.reflection_uid is None and again.used_source_ids==(),'a below-threshold or source-empty repeat does not append another belief or advance reflection progress'
    assert revision.affected==('meeting','unresolved') and revision.changed==('meeting',) and revision.unresolved==('unresolved',),'local revision reports every affected segment including an affected target without a replacement'
    current=revision.state.plans[0]
    assert current.uid=='meeting' and current.revision==1 and current.venue_uid=='cafe' and current.cause_ids==('raw-cause',),'a replaced plan retains its stable identity with the next revision and actual contradictory source causes'
    assert revision.state.plans[1:]==a.plans[1:] and current.start==10 and current.end==20,'unaffected plans and unresolved plans retain their complete original records while unrelated patches are ignored'
    future_state=replace(a,memories=(Memory('future-first',1,12,'observation','future',9),Memory('now-second',2,10,'observation','now',8)))
    now_result=reflect_from_sources(future_state,ReflectionProposal('r-now',3,'now',('now-second',)),10,5,8);later=reflect_from_sources(now_result.state,ReflectionProposal('r-later',4,'later',('future-first',)),12,5,8)
    assert later.used_source_ids==('future-first',) and later.state.progress.consumed_source_ids==('done','now-second','future-first'),'consuming an available later sequence does not consume or permanently skip an earlier future source'

    tie_state=replace(a,memories=(Memory('z-first',0,10,'observation','cafe',1),Memory('a-second',1,10,'observation','cafe',1)))
    assert tuple(m.uid for m in rank_memories(tie_state,10,5,'cafe',1))==('z-first',),'equal composite scores retain declaration priority at the top-k cutoff'
    gate_audit=reflect_from_sources(a,ReflectionProposal('gate-audit',22,'not due',('missing','future','prior-reflection','done','raw-cause')),10,5,100)
    assert gate_audit.state==a and gate_audit.used_source_ids==() and gate_audit.reflection_uid is None and gate_audit.rejected_source_ids==('missing','future','prior-reflection','done'),'citation rejection evidence remains complete when the reflection gate is below threshold'

@pytest.mark.skip('Part 4')
def test_current_plan_calendar_revision_cancellation_and_actual_fields(tmp_path):
    """Project current plan identity/revision, simulated interval, actor, venue and note through the complete supplied calendar classifier/writer/parser."""
    _,restored,_,revision=replayed(tmp_path);catalog=CalendarCatalog(restored.agents,venues());old=CalendarObservation('a',restored.agents[0].plans[0],'CONFIRMED');new=calendar_observations(revision)[0];cancel=replace(new,segment=replace(new.segment,revision=2,status='cancelled'),status='CANCELLED')
    class Source:
        def __init__(self,items):self.items=items;self.closed=False
        def __iter__(self):return iter(self.items)
        def close(self):self.closed=True
    source=Source((old,new,cancel));text=publish_calendar(source,lambda x:calendar_fields(x,catalog));rows=parse_calendar(text)
    assert source.closed and len(rows)==3 and text.endswith('END:VCALENDAR\r\n'),'the supplied calendar lifecycle emits every complete simulated event and closes the observation source'
    assert tuple(x['UID']for x in rows)==('simulated-meeting@smallville.local',)*3 and tuple(x['SEQUENCE']for x in rows)==(0,1,2),'plan revisions and cancellation update one stable calendar event rather than creating new identities'
    assert rows[1]['DTSTART']=='20260101T001000Z' and rows[1]['DTEND']=='20260101T002000Z' and rows[1]['X-AGENT']=='a' and rows[1]['SUMMARY']=='Alice','calendar evidence uses the actual current interval actor and sequence of the revised plan'
    assert rows[0]['LOCATION']=='Park' and rows[1]['LOCATION']=='Cafe; east,\nRoom' and rows[1]['DESCRIPTION']=='Meet; cafe,\nSIMULATED','each observation retains its own current venue and raw note through the supplied TEXT escaping'
    assert rows[-1]['STATUS']=='CANCELLED' and all(x['X-SIMULATED']=='TRUE'for x in rows),'cancellation keeps its actual status and every event declares simulated evidence'
    other=CalendarObservation('b',restored.agents[1].plans[0],'CONFIRMED');row=parse_calendar(publish_calendar((other,),lambda x:calendar_fields(x,catalog)))[0]
    assert row['UID']=='simulated-bob-meeting@smallville.local' and row['SUMMARY']=='Bob' and row['X-AGENT']=='b' and row['DESCRIPTION']=='Bob visit','independent observed agents keep their own event identity display name and plan note'

@pytest.mark.skip('Part 5')
def test_nested_current_plan_containment_open_hours_capacity_and_commit(tmp_path):
    """Execute authoritative revised action leaves through nested time containment, complete open intervals and one shared physical occupancy state."""
    _,restored,_,revision=replayed(tmp_path);b=restored.agents[1];b_revision=RevisionResult(b,(),(),());vs=venues()
    nodes=(PlanNode('day-a','a',0,40,children=('hour-a',)),PlanNode('hour-a','a',10,30,children=('action-a','future-a')),PlanNode('action-a','a',0,1,'meeting'),PlanNode('future-a','a',0,1,'work'),PlanNode('day-b','b',0,40,children=('action-b',)),PlanNode('action-b','b',0,1,'bob-meeting'))
    catalog=PlanCatalog((revision,b_revision),nodes,vs);roots=catalog.expand(('day-a','day-b'));world=World((('a','home'),('b','park')),vs);actual=execute_nested_plan(roots,world,12)
    assert actual.movements==(Movement('a','meeting','home','cafe'),) and actual.world.locations==( ('a','cafe'),('b','park')),'actual reopened revised plans move only an admitted current action and commit the shared physical world'
    hour=actual.reports[0].children[0];peer=actual.reports[1].children[0]
    assert actual.reports[0].status=='complete' and hour.path==('day-a','hour-a') and tuple(x.status for x in hour.children)==('moved','inactive') and peer.status=='full','every nested layer and inactive action is retained while later agents observe already committed venue capacity'
    reversed_run=execute_nested_plan(tuple(reversed(roots)),world,12)
    assert reversed_run.world.locations==( ('a','home'),('b','cafe')) and reversed_run.reports[1].children[0].children[0].status=='full','physical admission follows the declared execution order across independent agent plan trees'
    staying=execute_nested_plan(roots,replace(world,locations=(('a','cafe'),('b','park'))),12)
    assert staying.reports[0].children[0].children[0].status=='stayed' and not staying.movements,'an agent already at its target venue does not require another seat or invent a movement'
    outside_nodes=tuple(replace(n,end=19)if n.uid=='hour-a'else n for n in nodes);outside=execute_nested_plan(PlanCatalog((revision,b_revision),outside_nodes,vs).expand(('day-a',)),world,12)
    assert outside.reports[0].children[0].children[0].status=='outside-parent' and not outside.movements,'the complete authoritative action interval must fit its declared parent even when the current tick fits both'
    shortened=tuple(replace(v,open_intervals=((10,15),))if v.uid=='cafe'else v for v in vs);closed=execute_nested_plan(roots,replace(world,venues=shortened),12)
    assert closed.reports[0].children[0].children[0].status=='closed-venue' and closed.reports[1].children[0].status=='closed-venue' and not closed.movements,'admission requires the entire action interval within one venue opening rather than only the current tick'
    active_work=replace(revision,state=replace(revision.state,plans=(revision.state.plans[0],replace(revision.state.plans[1],start=10,end=18))+revision.state.plans[2:]));freed=execute_nested_plan(PlanCatalog((active_work,b_revision),nodes,vs).expand(('day-a','day-b')),world,12)
    assert tuple(m.destination for m in freed.movements)==('cafe','library','cafe') and freed.world.locations==( ('a','library'),('b','cafe')),'each actual departure releases physical capacity before later nested actions and peer plans execute'
    cancelled=replace(revision,state=replace(revision.state,plans=(replace(revision.state.plans[0],status='cancelled'),)+revision.state.plans[1:]));inactive=execute_nested_plan(PlanCatalog((cancelled,b_revision),nodes,vs).expand(('day-a',)),world,12)
    assert inactive.reports[0].children[0].children[0].status=='inactive' and not inactive.movements and inactive.world==world,'a current cancelled plan remains visible in the nested audit without executing a stale action'
    separate_openings=tuple(replace(v,open_intervals=((10,15),(16,21)))if v.uid=='cafe'else v for v in vs)
    gap_run=execute_nested_plan(roots,replace(world,venues=separate_openings),12)
    assert gap_run.reports[0].children[0].children[0].status=='closed-venue' and gap_run.reports[1].children[0].status=='closed-venue' and not gap_run.movements and gap_run.world.locations==world.locations,'a closure gap between separate venue openings cannot admit a spanning action'
    ancestor_nodes=tuple(replace(n,end=19)if n.uid=='day-a'else n for n in nodes)
    ancestor_run=execute_nested_plan(PlanCatalog((revision,b_revision),ancestor_nodes,vs).expand(('day-a',)),world,12)
    assert ancestor_run.reports[0].children[0].status=='outside-parent' and tuple(c.status for c in ancestor_run.reports[0].children[0].children)==('blocked','blocked') and not ancestor_run.movements and ancestor_run.world==world,'an outside-parent branch blocks all descendant actions while retaining their reports'
