"""Five locked parts for a proof-first slice decision service."""
import asyncio
import dataclasses
import json
import time
import pytest
from slicepick.model import Slice,Candidate,StopRule,Snapshot
from slicepick.selection import score,choose,decision,eligible
from slicepick.storage import DecisionStore
from slicepick.audit import Design,ProofNeed,effective_stop,select_testable
from slicepick.stream import pilot_stream
from slicepick.workflow import minimum_completion

def candidate(key='a',**changes):
    values=dict(name='read-only replay',outcome_value=5,uncertainty_reduced=5,effort=2,consequence=4,reversible=True,proves=('data','trust'))
    values.update(changes);return Candidate(key,Slice(**values))

def rule():return StopRule('bounded build','narrow authority','collect better evidence')

def parse_sse(packet):
    assert packet.endswith('\n\n'), 'SSE packets need a complete blank-line terminator'
    lines=packet[:-2].split('\n')
    assert len(lines)==2 and lines[0].startswith('event: ') and lines[1].startswith('data: '), 'one event and one JSON data line per packet'
    return lines[0][7:],json.loads(lines[1][6:])

@pytest.mark.skip('Part 1')
def test_slice_decision():
    """Repair positive-effort, reversibility, identity and wide proof coverage."""
    with pytest.raises(ValueError,match='effort must be positive'):
        decision([candidate('zero',effort=0,consequence=0)],{'data'})
    rev=candidate('rev');irrev=candidate('irrev',reversible=False)
    assert choose([irrev,rev],{'data'}).id=='rev', 'prefer reversible evidence when all other dimensions match'
    assert score(rev.slice)==2.5 and score(irrev.slice)==1.0, 'retain the declared consequence coefficients and rounding'
    a=candidate('a');b=candidate('b')
    report=decision([a,b],{' DATA '})
    assert report['selected']['id']=='b' and [x['id'] for x in report['alternatives']]==['a'], 'equal-content alternatives retain distinct candidate identities'
    raw=('trust',' DATA ','trust','extra');c=candidate('c',proves=raw)
    assert decision([c],{'data'})['selected']['proves']==raw, 'coverage comparison must not rewrite raw proof evidence'
    assert choose([candidate('cheap',proves=('trust',),effort=1,consequence=0),rev],{'data','trust'}).id=='rev', 'required proof gates numerical attractiveness'
    with pytest.raises(ValueError,match='no slice'): choose([rev],{'billing'})
    for required in (set(),{' '},('',)):
        with pytest.raises(ValueError,match='required proof'):choose([rev],required)
    with pytest.raises(ValueError,match='nonnegative integers'):score(dataclasses.replace(rev.slice,effort=True))
    original=[candidate('z'),candidate('a')];before=list(original)
    assert choose(original,{'trust'}).id=='z' and original==before, 'stable id tie-break must not mutate inputs'
    proofs=tuple(f'proof-{i:05d}' for i in range(13000));wide=candidate('wide',proves=proofs).slice
    start=time.perf_counter();covered=eligible(wide,set(proofs));elapsed=time.perf_counter()-start
    assert elapsed<.03, 'cover wide proof vocabularies without repeated tuple membership'
    assert covered and not eligible(wide,{'not-present'}), 'fast proof coverage must still test every requirement'

@pytest.mark.skip('Part 2')
def test_decision_snapshot(tmp_path):
    """JSON retains typed snapshot identity, exact score and raw decision evidence."""
    raw=' 证据 "raw"\nsecond line\r\n '
    a=candidate('z/opaque',name=raw,proves=(' TRUST ','data','data',raw));b=Candidate('a',a.slice)
    snapshot=Snapshot((' DATA ','trust','trust'),(a,b,candidate('irreversible',reversible=False)),'a',.10000000000000002,StopRule(raw,'stop','collect'))
    path=tmp_path/'state.json';DecisionStore(path).save(snapshot);loaded=DecisionStore(path).load()
    assert loaded==snapshot, 'snapshot must round-trip exact typed identities, raw proof order and stop-rule text'
    assert type(loaded) is Snapshot and type(loaded.candidates) is tuple and type(loaded.candidates[0]) is Candidate and type(loaded.candidates[0].slice) is Slice, 'restore nested snapshot dataclasses and tuples'
    assert type(loaded.candidates[0].slice.reversible) is bool and type(loaded.stop_rule) is StopRule, 'restore boolean and stop-rule types'
    assert loaded.candidates[2].slice.reversible is False, 'False is a recorded reversible value, not a missing field'
    assert loaded.selected_id=='a' and loaded.selected_score.hex()==snapshot.selected_score.hex(), 'selected id and exact stored float must not be recalculated'
    assert loaded is not DecisionStore(path).load() and loaded.candidates[0] is not DecisionStore(path).load().candidates[0], 'reopened snapshots are independent objects'
    negative=dataclasses.replace(snapshot,selected_score=-0.0,candidates=(a,),selected_id=a.id)
    DecisionStore(path).save(negative)
    assert DecisionStore(path).load()==negative and DecisionStore(path).load().selected_score.hex()==(-0.0).hex(), 'replacement removes stale candidates and preserves signed zero'
    before=path.read_bytes()
    with pytest.raises(ValueError,match='selected id'):DecisionStore(path).save(dataclasses.replace(snapshot,selected_id='missing'))
    assert path.read_bytes()==before, 'invalid selected identity must not replace the saved snapshot'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['candidates'][0]['slice']['proves']==list(a.slice.proves), 'JSON snapshot uses raw proof evidence rather than normalized comparison sets'

@pytest.mark.skip('Part 3')
def test_false_minimums_and_stop_rule():
    """Reject missing decision evidence, not merely a particular visual form."""
    need=ProofNeed(True,True,True,True)
    bad=Design(candidate('bad'), 'ui',False,False,False,True,StopRule('keep building',' KEEP   BUILDING ','keep building'))
    good=Design(candidate('good'), 'replay',True,True,True,False,rule())
    result=select_testable([bad,good],{'data','trust'},need)
    assert result=={'selected':'good','reasons':{'bad':('ui-only','infrastructure-only','happy-path','demo-only','platform-first','no-stop-rule'),'good':()}}, 'report all applicable false minimums in fixed order before selection'
    mock=Design(candidate('mock',proves=('comprehension',)),'ui',True,False,False,False,rule())
    assert select_testable([mock],{'comprehension'},ProofNeed(False,True,False,False))['selected']=='mock', 'a comprehension experiment may legitimately use a UI mock'
    unproven=Design(candidate('unproven',effort=0,consequence=0,proves=('trust',)),'replay',True,True,True,False,rule())
    result=select_testable([unproven,good],{'data'},need)
    assert result['selected']=='good' and result['reasons']['unproven']==('missing-proof',), 'proof-ineligible designs must not be scored'
    assert select_testable([bad],{'data'},need)['selected'] is None, 'no testable slice is a valid decision outcome'
    assert effective_stop(StopRule('keep building','change target user','keep building')), 'one decision-changing result makes the experiment meaningful'
    assert not effective_stop(StopRule('keep building','KEEP   BUILDING',' keep building ')), 'normalized keep-building for every result is not a stop rule'
    assert not effective_stop(StopRule('bounded build','stop','  ')), 'every result needs a nonblank action'
    assert not effective_stop(StopRule(' \t','stop','collect')), 'a pass result also needs a nonblank action'
    assert list(select_testable([good,bad],{'data'},need)['reasons'])==['good','bad'], 'reason entries retain design order even when ids sort differently'
    assert effective_stop(rule()), 'explicit non-building actions remain valid without a fixed keyword dictionary'
    assert select_testable([good],{' DATA '},need)['selected']=='good', 'false-minimum audit shares the normalized proof comparison gate'
    with pytest.raises(ValueError,match='required proof'):select_testable([good],set(),need)

@pytest.mark.skip('Part 4')
def test_pilot_stop_stream():
    """Consecutive errors trigger a decision after the current measurement, online."""
    async def scenario():
        r=StopRule('bounded build','narrow authority\n人工批准','collect better evidence');pulls=[]
        async def source():
            for value in (False,True,False,False):pulls.append(value);yield value
            raise AssertionError('a stopped pilot must not pull future outcomes')
        stream=pilot_stream(source(),r,2);first=await anext(stream)
        assert parse_sse(first)==('measurement',{'count':1,'correct':False,'errors':1}) and pulls==[False], 'emit the measurement before pulling the next outcome'
        rest=[parse_sse(packet) async for packet in stream]
        assert rest==[('measurement',{'count':2,'correct':True,'errors':0}),('measurement',{'count':3,'correct':False,'errors':1}),('measurement',{'count':4,'correct':False,'errors':2}),('decision',{'action':r.failed,'reason':'consecutive-errors'})], 'correct outcomes reset consecutive errors and terminal action follows its measurement'
        assert pulls==[False,True,False,False], 'stop without consuming any post-decision sample'
        pulls.clear();stream=pilot_stream(source(),r,2);await anext(stream);await stream.aclose()
        assert pulls==[False], 'closing at a yielded measurement cannot prefetch'
        async def completed():
            for value in (True,False,True):yield value
        ended=[parse_sse(x) async for x in pilot_stream(completed(),r,3)]
        assert ended[-1]==('decision',{'action':r.passed,'reason':'complete'}) and len(ended)==4, 'EOF after evidence emits the declared pass action exactly once'
        async def empty():
            if False:yield True
        assert [parse_sse(x) async for x in pilot_stream(empty(),r,1)]==[('decision',{'action':r.ambiguous,'reason':'no-evidence'})], 'no evidence uses the ambiguous action'
    asyncio.run(scenario())

@pytest.mark.skip('Part 5')
def test_vertical_workflow_completion():
    """A smallest slice is a connected proof path, including trigger and outcome."""
    graph={'trigger':('z','a'),'a':('join',),'z':('join',),'join':('outcome',),'outcome':(),'unrelated':()}
    built={'trigger','z','join','unrelated'}
    assert minimum_completion(graph,'trigger',{'outcome'},built)=={'path':('trigger','z','join','outcome'),'missing':('outcome',)}, 'minimize missing real workflow nodes rather than total path length'
    assert minimum_completion(graph,'trigger',{'outcome'},{'join'})=={'path':('trigger','a','join','outcome'),'missing':('trigger','a','outcome')}, 'equal-cost paths use the complete lexical path and count both endpoints'
    assert minimum_completion(graph,'outcome',{'outcome'},set())=={'path':('outcome',),'missing':('outcome',)}, 'trigger already equal to outcome still counts its missing node'
    assert minimum_completion(graph,'unrelated',{'outcome'},set()) is None, 'disconnected built nodes cannot be stitched into an outcome path'
    assert minimum_completion(graph,'trigger',{'join','outcome'},set())=={'path':('trigger','a','join'),'missing':('trigger','a','join')}, 'stop at the first observable outcome reached'
    tied={'t':('z','a'),'a':('middle',),'middle':('end',),'z':('end',),'end':()}
    assert minimum_completion(tied,'t',{'end'},{'t','a','middle','z'})=={'path':('t','a','middle','end'),'missing':('end',)}, 'equal missing cost uses full lexical path before any total-hop preference'
    before={k:tuple(v) for k,v in graph.items()};copy=set(built)
    minimum_completion(graph,'trigger',{'outcome'},built)
    assert graph==before and built==copy, 'workflow search must not mutate the graph or built set'
    for bad in ({'t':('t',)},{'t':('missing',)}):
        with pytest.raises(ValueError):minimum_completion(bad,'t',{'t'},set())
