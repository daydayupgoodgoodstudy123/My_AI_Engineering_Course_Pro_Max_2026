import asyncio
import copy
import csv
import io
import time
from dataclasses import replace
import pytest
from flowmap.audit import Evidence,Step,audit
from flowmap.store import WorkflowStore
from flowmap.discover import Finding,discover
from flowmap.recording import Event,segment
from flowmap.variants import Variant,variants

def evidence(level=1,confidence=0.9):return Evidence("recording α","observed current step",level,confidence)

@pytest.mark.skip("Part 1")
def test_workflow_evidence():
    """A grounded workflow needs strong evidence on every step and a reproducible evidence ratio."""
    artifact=Step(1,"engineer","opens runbook",(evidence(2),))
    assert audit([artifact])['status']=='grounded', "artifact evidence directly supports current behavior"
    weak=Step(2,"commander","approves write",(evidence(3,1.0),))
    assert audit([artifact,weak])['status']=='needs-evidence', "one observed step cannot ground the entire workflow"
    mixed=Step(1,"engineer","opens alert",(evidence(1),*(evidence(3) for _ in range(7))))
    assert audit([mixed])['direct_percent']==13, "evidence percentages round half up rather than half even"
    assert audit([replace(mixed,evidence=(evidence(4,1.0),))])['status']=='needs-evidence', "confidence cannot promote inferred behavior into direct evidence"
    assert audit([weak,artifact])['issues']==["workflow order must be contiguous from one"], "ordering is validated as recorded instead of silently sorted"
    invalid=Step(1,"engineer","acts",(evidence(0),evidence(1,1.1)))
    assert audit([invalid])['issues']==["step 1 has invalid evidence level","step 1 has invalid confidence"]
    assert audit([])['status']=='needs-evidence' and audit([])['direct_percent']==0, "no observed workflow is not a grounded workflow"
    steps=[Step(i+1,"engineer",f"observed action {i}",(evidence(2),),friction="context switch") for i in range(320)]
    start=time.perf_counter();report=audit(steps);elapsed=time.perf_counter()-start
    assert report['status']=='grounded' and len(report['steps'])==320
    assert report['steps'][7]['action']=='observed action 7', "display uses the correct observation position"
    assert elapsed<0.02, "render each step without rebuilding every other step"

@pytest.mark.skip("Part 2")
def test_workflow_store_roundtrip(tmp_path):
    """Workflow snapshots preserve evidence levels, confidence and multiple receipts in their recorded order."""
    first=Evidence("incident,184\n复盘","copied\tfield  ",2,0.1+0.2)
    second=Evidence("interview","reported workaround",3,0.99)
    rows=[Step(1,"on-call engineer","opens alert",(first,second),"three tools","chat","commander",True),Step(2,"commander","reviews",(second,first))]
    path=str(tmp_path/'workflows.db');store=WorkflowStore(path)
    store.save("team's α",rows);store.save('other',[rows[0]]);store.close()
    store=WorkflowStore(path)
    assert store.load("team's α")==rows, "all typed workflow fields and evidence order round-trip exactly"
    assert type(store.load("team's α")[0].evidence[0].level) is int, "evidence level remains an integer rather than directness bool"
    assert all(type(s.exception) is bool for s in store.load("team's α")), "snapshot exception values preserve bool type rather than integer equality"
    store.save("recorded",list(reversed(rows)))
    assert store.load("recorded")==list(reversed(rows)), "storage preserves recorded step order instead of applying audit policy"
    changed=[replace(rows[0],evidence=(second,))]
    store.save("team's α",changed);store.close();store=WorkflowStore(path)
    assert store.load("team's α")==changed and store.load('other')==[rows[0]], "replacing one workflow removes its old evidence without touching another workflow"
    store.save('empty',[])
    assert store.load('empty')==[], "an observed empty workflow is distinct from an unknown id"
    with pytest.raises(KeyError):store.load('missing')
    store.close()

@pytest.mark.skip("Part 3")
def test_four_things_and_handoffs():
    """Workflow risks retain exceptions and unconfirmed authority without inventing hidden state."""
    steps=[Step(1,"engineer","opens alert",(evidence(1),),friction="waits for lookup"),Step(2,"commander","missing deployment record",(evidence(3,1.0),),hidden_state="chat",authority="approves production write",exception=True),Step(3,"engineer","reconstructs service",(evidence(2,0.2),),authority="may read incident logs")]
    assert discover(steps)==[Finding("exception",2,"missing deployment record",False),Finding("handoff",2,"engineer -> commander",False),Finding("handoff",3,"commander -> engineer",False),Finding("hidden-state",2,"chat",False),Finding("authority",2,"approves production write",False),Finding("authority",3,"may read incident logs",True),Finding("friction",1,"waits for lookup",True)], "risk ordering preserves every finding and labels weak authority as unconfirmed"
    no_artifact=[Step(1,"a","acts",(evidence(3),)),Step(2,"b","continues",(evidence(3),))]
    assert [f.kind for f in discover(no_artifact)]==['handoff'], "an absent artifact does not by itself prove hidden state"
    assert discover([])==[]
    carriers=[Step(1,"engineer","first",(evidence(),),hidden_state="memory"),Step(2,"engineer","second",(evidence(),),hidden_state="personal-notes")]
    assert discover(carriers)==[Finding("hidden-state",1,"memory",True),Finding("hidden-state",2,"personal-notes",True)], "all explicitly allowed hidden-state carriers remain reportable"

async def event_source(events,pulled):
    for event in events:pulled.append(event);yield event

def collect(gen):
    async def run():return [x async for x in gen]
    return asyncio.run(run())

@pytest.mark.skip("Part 4")
def test_recording_segments():
    """A recording becomes actor/idle segments while preserving wait time and the final step."""
    events=[Event(0,"engineer, α","open"),Event(10,"engineer, α","copy"),Event(10,"commander","approve"),Event(25,"commander","recover"),Event(27,"commander","finish")]
    pulled=[];text=''.join(collect(segment(event_source(events,pulled),idle_ms=10)))
    assert list(csv.DictReader(io.StringIO(text)))==[{'step':'1','actor':'engineer, α','start':'0','end':'10','wait_ms':'0','events':'2'},{'step':'2','actor':'commander','start':'10','end':'10','wait_ms':'0','events':'1'},{'step':'3','actor':'commander','start':'25','end':'27','wait_ms':'15','events':'2'}], "actor changes, true idle gaps and stream tail remain distinct observed steps"
    assert pulled==events
    pulled=[]
    async def first():
        gen=segment(event_source(events,pulled));header=await gen.__anext__()
        assert header=='step,actor,start,end,wait_ms,events\n' and pulled==[], "header does not consume recording events"
        row=await gen.__anext__();await gen.aclose();return row
    assert list(csv.reader(io.StringIO(asyncio.run(first()))))[0]==['1','engineer, α','0','10','0','2'] and len(pulled)==3, "close a segment before pulling the next future event"
    assert collect(segment(event_source([],[])))==['step,actor,start,end,wait_ms,events\n']
    with pytest.raises(ValueError):collect(segment(event_source([],[]),idle_ms=-1))
    combined=[Event(0,"a","acts"),Event(15,"b","continues")]
    rows=list(csv.DictReader(io.StringIO("".join(collect(segment(event_source(combined,[]),idle_ms=10))))))
    assert rows[1]["wait_ms"]=="15", "a true idle wait belongs to the new segment even when actor also changes"
    custom=[Event(0,"a","one"),Event(5,"a","two"),Event(6,"a","three")]
    rows=list(csv.DictReader(io.StringIO("".join(collect(segment(event_source(custom,[]),idle_ms=4))))))
    assert [(r["start"],r["end"],r["wait_ms"],r["events"]) for r in rows]==[("0","0","0","1"),("5","6","5","2")], "a supplied idle threshold decides recording boundaries and waits"

def node(step,count,users,reasons,ends,children=()):return {'step':step,'count':count,'users':users,'reasons':reasons,'ends':ends,'children':list(children)}

@pytest.mark.skip("Part 5")
def test_observed_workflow_variants():
    """A prefix tree preserves real variant paths, shorter endpoints and reasons for disagreement."""
    open_step=("Engineer"," Open  Alert ");logs=("Engineer","Search Logs");runbook=("Engineer","Consult Runbook")
    observations=[Variant('short','ana','role',(open_step,)),Variant('long','bo','risk',(open_step,logs)),Variant('again','bo','risk',((" engineer ","open alert"),logs)),Variant('commander','cy',' ',(("Commander","Open Alert"),)),Variant('alternative','di','expertise',(open_step,runbook)),Variant('empty','ez','',())]
    before=copy.deepcopy(observations)
    expected=node(None,6,('ana','bo','cy','di','ez'),('role','risk','unknown','expertise'),('empty',),[
        node(('engineer','open alert'),4,('ana','bo','di'),('role','risk','expertise'),('short',),[
            node(('engineer','search logs'),2,('bo',),('risk',),('long','again')),
            node(('engineer','consult runbook'),1,('di',),('expertise',),('alternative',))]),
        node(('commander','open alert'),1,('cy',),('unknown',),('commander',))])
    assert variants(observations)==expected, "observations count separately while users, reasons and real terminal paths remain explicit"
    assert observations==before, "building variants does not reorder or rewrite observations"
    assert variants([])==node(None,0,(),(),()), "an empty collection has no invented workflow"
    tied=variants([Variant("z","one","role",(("Zed","acts"),)),Variant("a","two","role",(("Alpha","acts"),))])
    assert [child["step"] for child in tied["children"]]==[("alpha","acts"),("zed","acts")], "equal-count variant branches use normalized actor/action lexical order"
