"""Unlock one unchanged test at a time; supplied helpers stay public."""
import asyncio
import csv
import dataclasses
import json
import time
from pathlib import Path
import pytest
from riskmap.model import Assumption, Evidence, Experiment, Sample, Outcome, risk_score
from riskmap.ranking import map_decision, next_experiment, ranked_rows
from riskmap.storage import MapStore
from riskmap.experiments import judge
from riskmap.stream import stream_experiments
from riskmap.logic import assess_tree


def claim(key, score=5, verdict=None):
    return Assumption(key,'safety','The read-only result helps the on-call engineer',score,5,2,
                      None if verdict is None else Evidence(verdict,'raw evidence'))

def experiment(key='e',aid='a',**changes):
    values=dict(id=key,assumption_id=aid,population='on-call engineers',observable='correct service fraction',
                direction='at-least',threshold=.5,sample_size=2,registered_at='2026-01-01T00:00:00Z',
                pass_action='bounded build',fail_action='reframe or stop',ambiguous_action='collect more evidence')
    values.update(changes)
    return Experiment(**values)

def parse_log(line):
    result={};decoder=json.JSONDecoder();rest=line.rstrip('\n')
    while rest:
        key,tail=rest.split('=',1);value,end=decoder.raw_decode(tail)
        result[key]=value;rest=tail[end:].lstrip(' ')
    return result

@pytest.mark.skip('Part 1')
def test_assumption_map():
    """Resolve evidence polarity and open-risk selection before efficient ranking."""
    rejected=claim('rejected',5,'rejects');supported=claim('supported',4,'supports');opened=claim('open',3)
    decision=map_decision([rejected,supported,opened])
    assert decision['actions']['rejected']=='reframe-or-stop', 'rejecting evidence must change the build decision'
    assert decision['next']=='open', 'rejected assumptions are not unresolved experiment candidates'
    assert next_experiment([claim('z'),claim('a')])=='a', 'equal-risk selection must match the stable public ranking'
    assert next_experiment([supported,rejected]) is None, 'a decided map has no next experiment'
    assert next_experiment([claim('inc',2,'inconclusive')])=='inc', 'inconclusive evidence leaves an assumption open'
    assert map_decision([])=={'rows':[],'actions':{},'next':None}, 'an empty map is a valid empty decision'
    for value in (True,2.0,0,6):
        with pytest.raises(ValueError,match='risk dimensions'):
            risk_score(dataclasses.replace(opened,impact=value))
    assert risk_score(Assumption('x','value','condition',5,4,3))==23, 'retain the supplied example score'
    original=[claim('z',3),claim('a',5,'supports'),claim('b',5,'rejects')]
    assert ranked_rows(original)==[
        {'id':'a','score':27,'status':'supported','rank':1},
        {'id':'b','score':27,'status':'rejected','rank':2},
        {'id':'z','score':17,'status':'open','rank':3}], 'rank all statuses without changing caller order'
    assert [x.id for x in original]==['z','a','b'], 'ranking must not mutate caller inputs'
    large=[Assumption(f'{i:05d}','value','testable condition',i%5+1,(i//5)%5+1,1) for i in range(5000)]
    start=time.perf_counter();rows=ranked_rows(large);elapsed=time.perf_counter()-start
    assert elapsed<.08, 'generate risk ranks without comparing every pair'
    assert len(rows)==5000 and [r['rank'] for r in rows]==list(range(1,5001)), 'retain every consecutive one-based risk rank'
    assert [(r['score'],r['id']) for r in rows]==sorted([(risk_score(x),x.id) for x in large],key=lambda v:(-v[0],v[1])), 'fast ranks must retain scores and stable ties'

@pytest.mark.skip('Part 2')
def test_csv_map_roundtrip(tmp_path):
    """Round-trip both typed tables, including missing versus empty evidence."""
    raw='工程师, "yes"\nsecond line\r\nend'
    items=[Assumption('z/opaque','safety',' \t'+raw+'\n ',5,4,3,None),
           Assumption('a','value','different',1,2,5,Evidence('inconclusive','')),
           Assumption('b','feasibility','data exists',3,1,2,Evidence('rejects',raw)),
           Assumption('empty','viability','keep receipt',1,1,1,Evidence('',''))]
    exps=[experiment('z','z/opaque',population=raw,observable='Δ latency',threshold=.10000000000000002,
                     registered_at='2026-01-01T08:00:00.123456+08:00',fail_action=raw),
          experiment('a','a',direction='at-most',threshold=-0.0,sample_size=7)]
    location=tmp_path/'map';store=MapStore(location);store.save(items,exps)
    loaded,experiments=MapStore(location).load()
    assert (loaded,experiments)==(items,exps), 'CSV must preserve typed values, raw text and declared table order'
    assert all(type(x) is Assumption for x in loaded) and type(loaded[1].evidence) is Evidence, 'restore typed assumptions and evidence'
    assert all(type(x.impact) is int for x in loaded) and type(experiments[0].threshold) is float, 'restore dimensions and thresholds with declared types'
    assert experiments[0].threshold.hex()==exps[0].threshold.hex() and experiments[1].threshold.hex()==(-0.0).hex(), 'thresholds must preserve exact float values including signed zero'
    assert loaded[0].evidence is None and loaded[1].evidence==Evidence('inconclusive',''), 'missing evidence differs from an empty receipt'
    assert len(list(csv.reader((location/'assumptions.csv').open(newline='',encoding='utf-8'))))==4, 'use one real CSV record per assumption'
    loaded.pop();experiments.clear()
    assert MapStore(location).load()==(items,exps), 'loaded collections must be independent snapshots'
    store.save([items[1]],[exps[1]])
    assert MapStore(location).load()==([items[1]],[exps[1]]), 'saving replaces both tables without stale records'
    store.save([],[])
    assert MapStore(location).load()==([],[]), 'empty maps round-trip in both tables'

@pytest.mark.skip('Part 3')
def test_registered_experiment():
    """Decisions use pre-registered, inclusive, fixed-size evidence batches."""
    a=claim('a');e=experiment()
    samples=[Sample('2026-01-01T00:01:00Z',0),Sample('2026-01-01T00:02:00Z',1)]
    assert judge(a,e,samples)==Outcome('supported','bounded build',4), 'the inclusive threshold uses the mean, not the last observation'
    assert judge(a,dataclasses.replace(e,direction='at-most'),samples)==Outcome('supported','bounded build',4), 'at-most includes equality too'
    assert judge(a,dataclasses.replace(e,threshold=.6),samples)==Outcome('rejected','reframe or stop',4), 'negative evidence must produce its explicit fail action'
    assert judge(a,dataclasses.replace(e,direction='at-most',threshold=.4),samples).status=='rejected', 'at-most must not use the at-least comparison'
    assert judge(a,e,samples[:1])==Outcome('open','collect more evidence',5), 'partial evidence stays ambiguous without reducing uncertainty'
    assert judge(a,e,[])==Outcome('open','collect more evidence',5), 'an empty batch is ambiguous rather than a zero result'
    assert judge(dataclasses.replace(a,uncertainty=1),e,samples).uncertainty==1, 'decisive uncertainty never falls below one'
    assert judge(a,e,samples+[Sample('2025-01-01T00:00:00Z',-100)])==judge(a,e,samples), 'later arrivals cannot rewrite the first complete batch'
    for stamp in ('2026-01-01T00:01:00Z','2026-01-01T00:01:00.000001Z','2026-01-01T01:01:30+01:00'):
        with pytest.raises(ValueError,match='not pre-registered'):
            judge(a,dataclasses.replace(e,registered_at=stamp),samples)
    assert judge(a,dataclasses.replace(e,registered_at='2026-01-01T00:30:00+01:00'),samples).status=='supported', 'compare real instants rather than timestamp text'
    with pytest.raises(ValueError,match='not pre-registered'):
        judge(a,dataclasses.replace(e,registered_at='2026-01-01T00:01:30Z'),list(reversed(samples)))
    with pytest.raises(ValueError,match='assumption mismatch'):
        judge(claim('wrong'),e,samples)
    with pytest.raises(ValueError,match='not pre-registered'):
        judge(a,dataclasses.replace(e,registered_at='2026-01-01T00:02:00Z'),samples[:1])
    assert judge(a,dataclasses.replace(e,pass_action='human approval\nthen bounded build'),samples).decision=='human approval\nthen bounded build', 'explicit next actions are not hard-coded'

@pytest.mark.skip('Part 4')
def test_online_experiment_decisions():
    """Emit complete evidence promptly, stop on completion and flush partial EOF."""
    async def scenario():
        a=claim('a');b=claim('b');ea=experiment('a-e','a',sample_size=1,pass_action='批准 "yes"\nthen build');eb=experiment('b-e','b',sample_size=2)
        pulls=[]
        async def source():
            for event in [('a-e',Sample('2026-01-01T00:01:00Z',1)),('a-e',Sample('2026-01-01T00:02:00Z',-1)),('b-e',Sample('2026-01-01T00:03:00Z',0)),('b-e',Sample('2026-01-01T00:04:00Z',1))]:
                pulls.append(event[0]);yield event
            raise AssertionError('completed experiments must not pull future observations')
        stream=stream_experiments([a,b],[ea,eb],source())
        first=await anext(stream)
        assert pulls==['a-e'], 'emit each complete experiment before pulling another observation'
        assert first.endswith('\n') and first.count('\n')==1, 'logfmt is one physical line with supplied quoting'
        assert parse_log(first)=={'experiment':'a-e','status':'supported','decision':ea.pass_action,'uncertainty':4}, 'emit the actual judged outcome with raw action text'
        second=await anext(stream)
        assert parse_log(second)['experiment']=='b-e' and parse_log(second)['status']=='supported', 'independent experiments retain only their own first batch'
        with pytest.raises(StopAsyncIteration): await anext(stream)
        assert pulls==['a-e','a-e','b-e','b-e'], 'stop once every declared experiment has completed'
        # A consumer may cancel immediately after an emitted result.
        pulls.clear();stream=stream_experiments([a,b],[ea,eb],source());await anext(stream);await stream.aclose()
        assert pulls==['a-e'], 'closing after a yield must not prefetch'
        async def partial():
            yield 'b-e',Sample('2026-01-01T00:01:00Z',.9)
        lines=[parse_log(line) async for line in stream_experiments([a,b],[ea,eb],partial())]
        assert lines==[{'experiment':'a-e','status':'open','decision':ea.ambiguous_action,'uncertainty':5}, {'experiment':'b-e','status':'open','decision':eb.ambiguous_action,'uncertainty':5}], 'EOF flushes partial and empty batches in declared order'
        async def empty_source():
            if False: yield None
        eof=[parse_log(line)['experiment'] async for line in stream_experiments([a,b],[dataclasses.replace(ea,id='z-e'),dataclasses.replace(eb,id='a-e')],empty_source())]
        assert eof==['z-e','a-e'], 'EOF preserves declared experiment order even when ids sort differently'
        async def unused():
            raise AssertionError('empty plans must not consume observations')
            yield None
        assert [x async for x in stream_experiments([],[],unused())]==[], 'empty experiment plans produce no output'
    asyncio.run(scenario())

@pytest.mark.skip('Part 5')
def test_composite_assumptions():
    """Three-valued tree decisions select only still-influential open leaves."""
    items=[claim('ok',1,'supports'),claim('no',1,'rejects'),claim('high',5),claim('a',3),claim('z',3),claim('maybe',4,'inconclusive')]
    assert assess_tree({'all':['ok','no','high']},items)=={'status':'rejected','next':None}, 'a rejected conjunct decides ALL without more experiments'
    assert assess_tree({'any':['no','ok','high']},items)=={'status':'supported','next':None}, 'a supported alternative decides ANY without more experiments'
    assert assess_tree({'all':['ok',{'any':['no','a']},'z']},items)=={'status':'open','next':'a'}, 'open truth and stable risk ties propagate through mixed groups'
    tree={'all':[{'any':['ok','high']},{'any':['no','maybe']},'a','a']}
    before=json.dumps(tree,sort_keys=True)
    assert assess_tree(tree,items)=={'status':'open','next':'maybe'}, 'decided subtrees must not leak high-risk candidates into the root choice'
    assert assess_tree({'any':[{'all':['no','high']},'a']},items)=={'status':'open','next':'a'}, 'rejected subtrees contribute no actionable leaves'
    assert assess_tree('high',items)=={'status':'open','next':'high'}, 'a single leaf is a valid tree'
    assert assess_tree({'all':['ok','ok']},items)=={'status':'supported','next':None}, 'duplicate supported leaves preserve truth'
    assert assess_tree({'any':['no','no']},items)=={'status':'rejected','next':None}, 'all rejected alternatives remain rejected'
    assert json.dumps(tree,sort_keys=True)==before, 'tree assessment must not mutate the contract'
    for bad in ({'all':[]},{'any':['unknown']},{'other':['ok']}):
        with pytest.raises(ValueError): assess_tree(bad,items)
