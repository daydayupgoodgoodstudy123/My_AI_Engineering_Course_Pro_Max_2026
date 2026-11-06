import asyncio
import json
import time
from dataclasses import replace
import pytest
from promote.controls import Correction, ratchet, promote
from promote.records import ControlStore, Record
from promote.causes import Proposal, Selection, select_controls
from promote.stream import Observation, promoted
from promote.chain import Cause, Placement, place_controls

@pytest.mark.skip("Part 1")
def test_correction_pipeline():
    """Corrections become owned-layer controls only when recurrence or consequence earns it."""
    human=Correction("Product disagreement on public error", "Compatibility decision was implicit", 2,"minor")
    assert ratchet([human])[0].target=="human", "product disagreements become human decisions"
    assert ratchet([Correction("typo", "local preference",1,"minor")])==[], "a one-off preference does not earn a permanent control"
    severe=Correction("wrong result","edge case not checked",1,"severe")
    assert ratchet([severe])[0].target=="test", "a severe first occurrence earns a control"
    first=Correction("format escaped", " Format   Boundary. ",2,"minor")
    again=Correction("format escaped again", "format boundary",3,"severe")
    merged=ratchet([first,again])
    assert len(merged)==1, "equivalent cause spacing names one control"
    assert merged[0].recurrence==5 and merged[0].consequence=="severe", "independent correction counts add and severe consequence survives"
    assert (merged[0].cause,merged[0].symptom)==(first.cause,first.symptom), "canonical identity must not rewrite observed text"
    assert ratchet([Correction("preference","same cause",1,"minor")]*2)[0].recurrence==2, "group before deciding whether recurrence warrants promotion"
    records=[Correction("regression",f"missing case {i}",2,"minor") for i in range(4500)]
    start=time.perf_counter(); result=ratchet(records); elapsed=time.perf_counter()-start
    assert len(result)==4500 and result==sorted(result,key=lambda c:(c.target,c.fingerprint))
    assert elapsed<0.12, "batch promotion must not re-sort every growing prefix"

@pytest.mark.skip("Part 2")
def test_ratchet_record_roundtrip(tmp_path):
    """Ratchet snapshots preserve full correction evidence, ownership and review dates."""
    a=Record(promote(Correction("régression\n第二行\t "," Edge case 原因. ",7,"severe")),"team/研发", "2027-01-09")
    b=Record(promote(Correction("setup failed","environment missing",2,"minor")),"ops", "2026-12-31")
    path=str(tmp_path/'controls.db')
    store=ControlStore(path); store.save(a); store.save(b)
    assert store.records()==[a,b], "every ratchet field round-trips as its original value and type"
    changed=replace(a,control=replace(a.control,recurrence=11),owner="new owner",review_date="2027-03-01")
    store.save(changed); store.save(changed); store.close()
    store=ControlStore(path)
    assert store.records()==[changed,b], "save replaces a snapshot instead of adding its already accumulated recurrence"
    assert store.records("automation")==[b] and store.records("human")==[], "target selection reads stored owning layers"
    assert type(store.records()[0].control.recurrence) is int, "recurrence stays an integer"
    store.close()
    record=Record(promote(Correction("regression","missing branch",2,"minor")),"","after next pilot")
    store=ControlStore(str(tmp_path/'empty-owner.db')); store.save(record); store.close()
    store=ControlStore(str(tmp_path/'empty-owner.db'))
    assert store.records()==[record], "storage preserves empty owner and a free-form review date"
    store.close()

@pytest.mark.skip("Part 3")
def test_cause_not_symptom():
    """A shared symptom can hide different causes; only effective verified controls qualify."""
    rows=[Correction("README edited","scope too broad",2,"minor"),Correction("README edited","format unspecified",1,"severe"),Correction("another file edited"," SCOPE TOO BROAD. ",3,"minor")]
    options=[Proposal("scope-z","scope",("scope too broad",),"Restrict writable paths",True),Proposal("scope-a","scope",("scope too broad",),"Reject extra paths",True),Proposal("symptom","example",("scope too broad",)," README EDITED. ",True),Proposal("untested","example",("scope too broad",),"Prevent off-scope writes",False),Proposal("wrong-cause","example",("other cause",),"Use an example",True),Proposal("format","example",("format unspecified",),"Validate output shape",True),Proposal("late","instruction",("format unspecified",),"Remember the schema",True)]
    assert select_controls(rows,options)==[Selection("scope too broad",("README edited","another file edited"),5,"scope-a"),Selection("format unspecified",("README edited",),1,"format")], "each cause gets its own effective control, with original symptoms and summed observations"
    product=[Correction("Product disagreement","which public status",2,"minor")]
    assert select_controls(product,[Proposal("auto","example",("which public status",),"Change status",True),Proposal("decision","human",("which public status",),"Record compatibility choice",True)])[0].proposal=="decision", "product judgment cannot be reassigned to an executable layer"
    assert select_controls(rows,[])[0].proposal is None, "no effective control remains an explicit gap"
    assert select_controls([],options)==[]
    same_cause=[Correction("first symptom","one cause",2,"minor"),Correction("second symptom","one cause",1,"minor")]
    choices=[Proposal("bad","example",("one cause",)," SECOND   SYMPTOM. ",True),Proposal("good","scope",("one cause",),"Limit writable paths",True)]
    assert select_controls(same_cause,choices)[0].proposal=="good", "rule repeating any grouped symptom is not an effective control"

async def source(events,pulled):
    for event in events:
        pulled.append(event); yield event

def collect(gen):
    async def run(): return [x async for x in gen]
    return asyncio.run(run())

def parse(text):
    records=[]
    for block in text.split('\n\n')[:-1]:
        event,data=block.split('\n')
        assert event=='event: promoted' and data.startswith('data: '), "promotion events follow the supplied SSE view"
        records.append(json.loads(data[6:]))
    return records

@pytest.mark.skip("Part 4")
def test_online_promotion():
    """A severe correction promotes now; recurring corrections use their bounded evidence window."""
    events=[Observation(0,"cause A","minor"),Observation(10,"cause A","minor"),Observation(11," Cause  A. ","minor"),Observation(12,"cause A","minor"),Observation(13,"cause B","severe"),Observation(14,"cause C","minor"),Observation(15,"cause C","minor")]
    pulled=[]
    assert parse(''.join(collect(promoted(source(events,pulled)))))==[{"cause":"cause a","count":2,"at":11},{"cause":"cause b","count":1,"at":13},{"cause":"cause c","count":2,"at":15}], "window expiry and severe consequence decide promotions without ending other causes"
    assert pulled==events
    pulled=[]
    async def first():
        gen=promoted(source(events,pulled)); row=await gen.__anext__(); await gen.aclose(); return row
    assert parse(asyncio.run(first()))[0]['at']==11 and len(pulled)==3, "emit before pulling future corrections"
    assert collect(promoted(source([],[])))==[]
    with pytest.raises(ValueError): collect(promoted(source([],[]),threshold=0))
    custom=[Observation(0,"cause","minor"),Observation(1,"cause","minor"),Observation(2,"cause","minor")]
    assert parse(''.join(collect(promoted(source(custom,[]),threshold=3))))==[{"cause":"cause","count":3,"at":2}], "custom recurrence threshold controls the triggering observation"

@pytest.mark.skip("Part 5")
def test_effective_owner_in_why_graph():
    """A why-DAG places each correction at its deepest effective owned cause, retaining all symptoms."""
    shared=Cause("Missing executable boundary","scope",True)
    deep=Cause("intermediate",None,False,[shared])
    root=Cause("broad symptom","instruction",True,[shared,Cause("context",None,False,[deep])])
    second=Cause("another path",None,False,[shared])
    assert place_controls([("README edited",root),("other file edited",second),("README edited",root)])==[Placement("missing executable boundary","scope",("README edited","other file edited"))], "shared causes merge symptoms after their deepest effective placement"
    tie=Cause("root","instruction",True,[Cause("z cause","test",True),Cause("a cause","automation",True),Cause("deeper unverified","scope",False,[Cause("deep owner",None,True)])])
    assert place_controls([("symptom",tie)])==[Placement("a cause","automation",("symptom",))], "unowned or ineffective causes cannot defeat a valid depth tie"
    a=Cause("a","test",True); branch=Cause("middle","scope",True,[a])
    root=Cause("root","instruction",True,[a,branch,Cause("z","automation",True)])
    assert place_controls([("s",root)])[0].cause=='a', "a shared cause must be considered at every path depth"
    with pytest.raises(ValueError): place_controls([("unplaced",Cause("no owner"))])
    assert place_controls([])==[]
    shared_z=Cause("z cause","test",True)
    deep=Cause("root",None,False,[shared_z,Cause("bridge",None,False,[shared_z]),Cause("a cause","scope",True)])
    assert place_controls([("symptom",deep)])==[Placement("z cause","test",("symptom",))], "deeper occurrence of shared cause defeats a shallower lexical competitor"
    z=Cause("z cause","test",True); a=Cause("a cause","scope",True)
    untouched=Cause("root",None,False,[z,a]); before=tuple(id(child) for child in untouched.why)
    assert place_controls([("symptom",untouched)])==[Placement("a cause","scope",("symptom",))]
    assert tuple(id(child) for child in untouched.why)==before, "placing controls does not reorder input DAG children"
