import asyncio,copy,csv,json,time
from dataclasses import replace
from datetime import date,timedelta
import pytest
from ratchet.actions import Signal,Action,TARGETS,destination,backlog,promote,schedule
from ratchet.ledger import Ledger,HEADER
from ratchet.retirement import Evidence,Review,Verdict,assess
from ratchet.stream import ratchet
from ratchet.lineage import Control,active_controls
TODAY=date(2026,11,5)
def signal(key='incident',**kw):
    values=dict(fingerprint=key,sources=('incident 184',),observation='stale fact caused duplicate lookup',severity=3,frequency=1,owner='platform',days=90,observed_on='2026-10-01',impacts=('workbench',));values.update(kw);return Signal(**values)
def action(**kw):
    values=dict(id='control',fingerprint='cause',track='workbench',destination='context',priority=9,owner='platform',artifact='context/retrieval-guidance.md',verification='replay with context',promoted_on='2026-01-01',review_on='2026-12-01',retirement='review with evidence',sources=('incident',));values.update(kw);return Action(**values)
def review(**kw):
    values=dict(window_days=90,last_recurrence='2026-11-01',blocked_legitimate=0,prevented_harm=1,architecture_changed=False,evidence=Evidence('control','workbench'));values.update(kw);return Review(**values)

@pytest.mark.skip('Part 1')
def test_owned_feedback_actions():
    """Repair target metadata, both affected tracks and the review lifetime without repeating routing defects."""
    s=signal();before=copy.deepcopy(s);a=backlog([s],TODAY)[0]
    assert (a.artifact,a.verification)==TARGETS[('workbench','context')], 'artifact and verification belong to the chosen control target'
    both=signal(impacts=('product','workbench'));actions=promote(both,TODAY)
    assert [(a.track,a.destination) for a in actions]==[('product','backlog'),('workbench','context')], 'an incident can own both product and coding-agent changes'
    assert all(a.promoted_on=='2026-11-05' and a.review_on=='2027-02-03' for a in actions), 'a new control review window starts at promotion rather than an old observation'
    combined=backlog([signal(frequency=2),signal(sources=('pilot audit',),severity=5,frequency=3)],TODAY)[0]
    assert combined.priority==25 and combined.sources==('incident 184','pilot audit'), 'correct supplied merge retains recurrence and evidence provenance'
    assert destination(signal(observation='retry storm'))=='runtime' and destination(signal(observation='authority gap'))=='policy'
    assert destination(signal(observation='new product need'))=='backlog' and s==before
    with pytest.raises(ValueError,match='owner'):promote(signal(owner=' \t'),TODAY)
    assert schedule(TODAY,[60,90,180])==['2027-01-04','2027-02-03','2027-05-04'], 'ordinary sixty ninety and one-eighty day windows retain calendar boundaries'
    windows=[180]*6000
    start=time.perf_counter();dates=schedule(TODAY,windows);elapsed=time.perf_counter()-start
    assert dates==[(TODAY+timedelta(days=d)).isoformat() for d in windows], 'date scheduling preserves ordinary calendar windows and order'
    assert elapsed<0.014, 'schedule review dates without advancing one day at a time'

@pytest.mark.skip('Part 2')
def test_control_csv_history(tmp_path):
    """Full historical controls retain proof owner raw text and independent track identity."""
    raw=' "review", 人工\r\nline\t end\u2028paragraph\u0085next '
    first=action(owner=' platform α ',retirement=raw,verification='cmd --arg "x,y"\nnext',sources=('incident\n184','pilot α'))
    product=action(id='product-control',track='product',artifact='product/outcome-frame.md',priority=17)
    changed=replace(first,priority=11,verification='new proof',review_on='2027-01-01')
    path=tmp_path/'controls.csv';ledger=Ledger(path)
    assert ledger.entries()==[]
    for a in (first,product,changed):ledger.append(a)
    reopened=Ledger(path)
    assert reopened.entries()==[(1,first),(2,product),(3,changed)], 'CSV revisions reconstruct every exact typed action including embedded line separators'
    assert reopened.history(first.artifact)==[(1,first),(3,changed)], 'artifact history retains earlier controls and later revisions in physical order'
    assert reopened.history('missing')==[] and type(reopened.entries()[0][1].priority) is int
    assert type(reopened.entries()[0][1].sources) is tuple and reopened.entries()[0][1].owner==' platform α '
    with path.open(encoding='utf-8',newline='') as f:
        reader=csv.reader(f);assert tuple(next(reader))==HEADER
    empty=tmp_path/'empty.csv';empty.touch();Ledger(empty).append(product)
    assert Ledger(empty).entries()==[(1,product)], 'an existing empty ledger still needs a CSV header'
    reopened.append(replace(first,id='prefix-only',artifact=first.artifact+'-extra'))
    assert reopened.history(first.artifact)==[(1,first),(3,changed)], 'artifact history matches the exact artifact path rather than a lexical prefix'
    # Each review observation is a new control-history record, even when unchanged.
    reopened.append(first)
    same_artifact_product=replace(product,artifact=first.artifact)
    Ledger(path).append(same_artifact_product)
    expected_history=[(1,first),(3,changed),(5,first),(6,same_artifact_product)]
    assert Ledger(path).history(first.artifact)==expected_history, 'repeat observations and both impact tracks retain their own globally numbered history'
    assert [revision for revision,_ in reopened.entries()]==[1,2,3,4,5,6], 'revision numbers continue globally across artifacts tracks and reopened handles'
    Ledger(path).append(first)
    assert reopened.history(first.artifact)==expected_history+[(7,first)], 'a live ledger reads later appends without caching or coalescing identical Actions'

@pytest.mark.skip('Part 3')
def test_evidence_before_retirement():
    """Architecture age and obstruction trigger review; only qualified evidence can justify retirement."""
    c=action();base=review()
    assert assess(c,TODAY,base)==Verdict('keep',()), 'recent recurrence and a future review date keep the existing control'
    assert assess(c,TODAY,replace(base,architecture_changed=True))==Verdict('review',('architecture',)), 'architecture change requests review rather than automatic deletion'
    approved=Evidence(c.id,c.track,True,False,'lower-level',True,True,True)
    assert assess(c,TODAY,replace(base,evidence=approved))==Verdict('retire',('replacement',)), 'a verified covering replacement and explicit approval can retire the old control'
    pending=replace(approved,replacement_verified=False)
    due=replace(c,review_on=TODAY.isoformat())
    assert assess(due,TODAY,replace(base,evidence=pending))==Verdict('review',('due',)), 'an unverified replacement cannot retire a due control'
    quiet=replace(base,last_recurrence=None,blocked_legitimate=2,prevented_harm=1)
    assert assess(c,TODAY,quiet)==Verdict('review',('no-recorded-recurrence','obstruction')), 'an old quiet control still needs observed window evidence and approval'
    observed=Evidence(c.id,c.track,True,True,retirement_approved=True)
    assert assess(c,TODAY,replace(quiet,evidence=observed)).status=='retire'
    boundary=(TODAY-timedelta(days=90)).isoformat()
    assert assess(c,TODAY,replace(base,last_recurrence=boundary)).status=='keep', 'a recurrence at the window start is inside the protected window'
    assert assess(c,TODAY,replace(base,blocked_legitimate=1,prevented_harm=1)).status=='keep', 'equal interception counts do not mean more legitimate work was blocked'
    wrong=replace(observed,control_id='another')
    assert assess(c,TODAY,replace(quiet,evidence=wrong)).status=='review', 'correct supplied evidence qualification rejects an unrelated retirement receipt'
    assert assess(replace(c,promoted_on=TODAY.isoformat()),TODAY,replace(base,last_recurrence=None))==Verdict('keep',()), 'a newly promoted control has not existed for a complete quiet window'
    unobserved=Evidence(c.id,c.track,verified=True,retirement_approved=True)
    assert assess(c,TODAY,replace(base,last_recurrence=None,evidence=unobserved))==Verdict('review',('no-recorded-recurrence',)), 'approval cannot replace full observed-window evidence for quiet retirement'

async def arrivals(rows,pulled):
    for s in rows:pulled.append(s);yield s

def collect(gen):
    async def run():return [x async for x in gen]
    return asyncio.run(run())

@pytest.mark.skip('Part 4')
def test_multisource_ratchet_stream():
    """Merged evidence promotes all owned action identities immediately while other causes continue."""
    first=signal(impacts=('product','workbench'));second=signal(sources=('pilot audit',));other=signal('other',observation='timeout',severity=5);later=signal(sources=('evaluation',),frequency=9)
    rows=[first,second,other,later];pulled=[];lines=collect(ratchet(arrivals(rows,pulled),TODAY,threshold=5));packets=[json.loads(x) for x in lines]
    assert [(x['fingerprint'],x['track'],x['destination'],x['priority']) for x in packets]==[('incident','product','backlog',6),('incident','workbench','context',6),('other','workbench','runtime',5)], 'merged threshold materializes every track and continues other causes'
    assert packets[0]['sources']==['incident 184','pilot audit'] and packets[0]['priority']==6 and len(lines)==3, 'emitted actions retain their triggering source snapshot rather than future evidence'
    assert pulled==rows and all(x.endswith('\n') for x in lines)
    async def boundary():
        pulled=[];gen=ratchet(arrivals(rows,pulled),TODAY,5);a=await gen.__anext__();b=await gen.__anext__()
        assert [json.loads(a),json.loads(b)]==packets[:2] and len(pulled)==2, 'complete the current multi-impact action block before a future signal'
        await gen.aclose();assert len(pulled)==2, 'closing an action stream cannot pull future evidence'
    asyncio.run(boundary())
    assert collect(ratchet(arrivals([],[]),TODAY,5))==[]
    later_impact=[signal(),signal(sources=('pilot audit',),impacts=('product',))]
    extended=[json.loads(x) for x in collect(ratchet(arrivals(later_impact,[]),TODAY,3))]
    assert [(x['track'],x['priority'],x['sources']) for x in extended]==[('workbench',3,['incident 184']),('product',6,['incident 184','pilot audit'])], 'a later new impact creates its own action even after the first track was promoted'

@pytest.mark.skip('Part 5')
def test_control_replacement_lineage():
    """Verified transitive replacement suppresses ancestors and retirement reactivates the correct fallback."""
    nodes=[Control('a','cause','workbench'),Control('b','cause','workbench',supersedes=('a',)),Control('c','cause','workbench',supersedes=('b',)),Control('product','cause','product')]
    impacts=[('cause','product'),('cause','workbench'),('unknown','workbench')];before=copy.deepcopy(nodes)
    assert active_controls(nodes,impacts)=={('cause','product'):('product',),('cause','workbench'):('c',),('unknown','workbench'):()}, 'transitive replacement preserves both product and workbench control impacts'
    retired=[replace(n,retired=True) if n.id=='c' else n for n in nodes]
    assert active_controls(retired,impacts)[('cause','workbench')]==('b',), 'retiring the newest control revives its predecessor without reviving every ancestor'
    retired=[replace(n,retired=True) if n.id in ('b','c') else n for n in nodes]
    assert active_controls(retired,impacts)[('cause','workbench')]==('a',)
    pending=[replace(n,verified=False) if n.id=='c' else n for n in nodes]
    assert active_controls(pending,impacts)[('cause','workbench')]==('b',), 'an unverified replacement does not suppress an existing effective control'
    middle_retired=[replace(n,retired=True) if n.id=='b' else n for n in nodes]
    assert active_controls(middle_retired,impacts)[('cause','workbench')]==('c',), 'historical coverage traverses a retired intermediate control'
    assert nodes==before, 'lineage review cannot mutate saved control history'
    chain=[Control(str(i),'long','workbench',supersedes=(str(i-1),) if i else ()) for i in range(1100)]
    assert active_controls(chain,[('long','workbench')])=={('long','workbench'):('1099',)}, 'the supplied lineage schema handles general finite chains iteratively'
    with pytest.raises(ValueError,match='cycle'):active_controls([replace(nodes[0],supersedes=('c',)),*nodes[1:]],impacts)
    with pytest.raises(ValueError,match='identity'):active_controls([replace(nodes[0],supersedes=('product',)),*nodes[1:]],impacts)
    concurrent=[Control('z','cause','workbench'),Control('a','cause','workbench')]
    assert active_controls(concurrent,[('cause','workbench')])=={('cause','workbench'):('a','z')}, 'concurrently effective controls are returned in sorted id order'
