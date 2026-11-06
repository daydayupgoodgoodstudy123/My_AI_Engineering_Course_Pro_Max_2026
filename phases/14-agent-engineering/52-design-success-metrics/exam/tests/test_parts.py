import asyncio,copy,json,time
from dataclasses import replace
import pytest
from metricplan.contract import Metric,Plan,report,read_source
from metricplan.replays import Replay,ReplayStore
from metricplan.decision import DecisionPlan,Decision,decide
from metricplan.pilot import pilot,tap_rows
from metricplan.gqm import Question,Goal,trace

def metrics():
    return [Metric('speed','at-most',120,'ten replays','replay log','on-call engineers','outcome'),Metric('writes','at-most',0,'entire pilot','audit log','on-call engineers','guardrail'),Metric('workload','at-most',10,'entire pilot','operator log','on-call engineers','counter')]
def source(path,payload):path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');return path

def replay(key,ms=120000,correct=True,**kw):
    values=dict(id=key,incident='incident α',elapsed_ms=ms,correct=correct,writes=0,at='2026-11-01T00:00:00Z',population='on-call engineers',included=True);values.update(kw);return Replay(**values)

@pytest.mark.skip('Part 1')
def test_metric_contract_report(tmp_path):
    """Repair population validation, report all metric roles and read reproducible source snapshots efficiently."""
    ms=metrics();plan=Plan('Reduce diagnosis time safely',('How fast?','Still read-only?'),tuple(ms))
    path=source(tmp_path/'source.json',{'values':{'speed':120,'writes':0,'workload':10},'receipt':'pilot α'})
    invalid=replace(plan,metrics=(replace(ms[0],population=''),*ms[1:]))
    assert report(invalid,path)['status']=='invalid' and 'speed lacks population' in report(invalid,path)['issues'], 'a metric without its population is not a reproducible contract'
    result=report(plan,path)
    assert result['results']==[{'name':'speed','value':120,'passed':True},{'name':'writes','value':0,'passed':True},{'name':'workload','value':10,'passed':True}], 'counter metrics remain visible beside outcomes and guardrails'
    assert result['status']=='valid' and result['plan']['metrics'][0]['population']=='on-call engineers'
    assert read_source(path)=={'values':{'speed':120,'writes':0,'workload':10},'receipt':'pilot α'}, 'reading a source snapshot preserves every receipt and Unicode field'
    source(path,{'values':{'speed':float('nan'),'writes':0}})
    assert report(plan,path)['results']==[{'name':'speed','status':'invalid'},{'name':'writes','value':0,'passed':True},{'name':'workload','status':'missing'}], 'finite validation and missing values remain distinct'
    duplicate=replace(plan,metrics=(*plan.metrics,ms[0]))
    assert 'duplicate metric: speed' in report(duplicate,path)['issues'], 'metric names identify one unambiguous contract'
    for changes in ({'direction':'up'},{'threshold':float('inf')},{'kind':'dashboard'}):
        bad=replace(plan,metrics=(replace(ms[0],**changes),*ms[1:]))
        assert report(bad,path)['status']=='invalid'
    payload={'values':{'speed':94,'writes':0,'workload':4},'receipts':[{'source':f'pilot-event-{i}','observation':'Read alert; inspect service logs; no production writes. '*4} for i in range(4000)]}
    source(path,payload)
    start=time.perf_counter();loaded=read_source(path);elapsed=time.perf_counter()-start
    assert loaded==payload, 'reading a source snapshot preserves every receipt and Unicode field'
    assert elapsed<0.04, 'read a bounded source snapshot without a system call for every byte'

@pytest.mark.skip('Part 2')
def test_replay_store_roundtrip(tmp_path):
    """Raw replay evidence survives reopen; latest selection follows observed instants rather than insertion ids."""
    rows=[replay('late',120001,False,incident='alert, α\nline\r\n\t ',at='2026-11-02T00:00:00Z'),replay('early',119999,True,at='2026-11-02T01:00:00+02:00'),replay('tie',0,False,at='2026-11-02T00:00:00+00:00',included=False)]
    path=str(tmp_path/'replays.db');store=ReplayStore(path)
    for r in rows:store.put(r)
    store.put(replay('other',population='another team',at='2026-11-03T00:00:00Z'));store.close();store=ReplayStore(path)
    assert [store.get(r.id) for r in rows]==rows, 'replay milliseconds population receipt text and exclusion flags round-trip exactly'
    assert type(store.get('late').correct) is bool and type(store.get('late').elapsed_ms) is int
    assert store.recent('on-call engineers',2)==[rows[0],rows[2]], 'latest evidence uses true instants and stable ids then returns oldest first'
    store.put(replay('z-old',population='clock-order',at='2026-11-01T00:00:00Z'));store.put(replay('a-new',population='clock-order',at='2026-11-03T00:00:00Z'))
    assert [r.id for r in store.recent('clock-order',1)]==['a-new'], 'latest evidence uses true instants and stable ids then returns oldest first'
    updated=replay('z-old',population='clock-order',at='2026-11-04T00:00:00Z');store.put(updated)
    assert store.recent('clock-order',1)==[updated], 'replacing a replay must update its indexed instant as well as its payload'
    assert store.recent('on-call engineers',0)==[] and store.recent('missing',3)==[]
    changed=replace(rows[0],elapsed_ms=1,writes=2,population='another team');store.put(changed);store.close();store=ReplayStore(path)
    assert store.get('late')==changed and store.recent('on-call engineers',10)==[rows[1],rows[2]], 'replacing a replay updates its indexed population and preserves other evidence'
    with pytest.raises(KeyError):store.get('missing')
    with pytest.raises(ValueError):store.recent('on-call engineers',-1)
    store.close()

@pytest.mark.skip('Part 3')
def test_predeclared_measurement_decision():
    """A full fixed replay batch and the entire pilot jointly determine pass fail or ambiguous."""
    plan=DecisionPlan('on-call engineers');rows=[replay(str(i),110000 if i<5 else 130000,i!=9) for i in range(10)];before=copy.deepcopy(rows)
    assert decide(plan,plan,rows)==Decision('pass',0.9,120,0,10), 'inclusive accuracy and even median jointly meet the registered pass contract'
    unsafe=[*rows,replay('excluded',included=False,writes=1)]
    assert decide(plan,plan,unsafe).status=='fail', 'pilot writes fail even when excluded from the outcome denominator'
    wrong_population=replay('other',population='other',elapsed_ms=999999)
    assert decide(plan,plan,[wrong_population,*rows]).used==10 and decide(plan,plan,[wrong_population,*rows]).median_seconds==120
    assert decide(plan,plan,rows,workload=11).status=='ambiguous', 'counter metric deterioration downgrades a passing local improvement'
    failed=[replace(r,correct=i<7) for i,r in enumerate(rows)]
    assert decide(plan,plan,failed,workload=11).status=='fail', 'fail evidence outranks both passing speed and counter ambiguity'
    assert decide(plan,plan,[replay('one',correct=False)]).status=='ambiguous' and decide(plan,plan,[]).accuracy is None, 'incomplete evidence is not a zero-percent failure'
    assert decide(replace(plan,batch_size=4),replace(plan,batch_size=4),[replay(str(i),correct=i<3) for i in range(4)]).status=='ambiguous', 'accuracy at the fail floor is not below the floor'
    with pytest.raises(ValueError,match='contract changed'):decide(replace(plan,max_seconds=999),plan,rows)
    assert rows==before, 'measurement cannot rewrite the original replay evidence'
    assert decide(plan,plan,[replace(r,elapsed_ms=130000) for r in rows]).status=='ambiguous', 'passing accuracy cannot bypass the registered speed threshold'
    short=replace(plan,batch_size=2);first=[replay('first'),replay('second'),replay('late',correct=False)]
    chosen=decide(short,short,first)
    assert chosen.status=='pass' and chosen.accuracy==1.0, 'later arrivals do not replace the first registered outcome batch'

def collect(gen):
    async def run():return [x async for x in gen]
    return asyncio.run(run())
async def arrivals(rows,pulled):
    for r in rows:pulled.append(r);yield r

@pytest.mark.skip('Part 4')
def test_pilot_metric_stream():
    """Fixed batches emit complete metric blocks; any pilot write stops before later observations."""
    plan=DecisionPlan('on-call engineers',batch_size=2);rows=[replay('a'),replay('b'),replay('ignored',population='other'),replay('partial',100000)]
    expected=tap_rows(Decision('pass',1.0,120.0,0,2),1,1)+tap_rows(Decision('ambiguous',1.0,100.0,0,1),2,4)
    pulled=[]
    assert collect(pilot(plan,arrivals(rows,pulled)))==expected, 'fixed disjoint windows keep global numbering and flush only a real partial batch'
    assert pulled==rows
    excluded=replay('unsafe',included=False,writes=1)
    assert collect(pilot(plan,arrivals([rows[0],excluded,replay('future')],[])))==['Bail out! production write\n'], 'a write bails out before a success window even when its replay is excluded'
    assert collect(pilot(plan,arrivals([],[])))==[] and collect(pilot(plan,arrivals([rows[2]],[])))==[], 'empty outcome windows emit no fictitious metrics'
    async def boundary():
        pulled=[];gen=pilot(plan,arrivals(rows,pulled));first=await gen.__anext__()
        assert first==expected[0] and len(pulled)==2, 'emit the completed batch before pulling a future record'
        second=await gen.__anext__();third=await gen.__anext__()
        assert [first,second,third]==expected[:3] and len(pulled)==2, 'all metrics from one batch precede the next source pull'
        await gen.aclose();assert len(pulled)==2, 'closing after a metric row does not prefetch'
    asyncio.run(boundary())
    other_write=replay('unsafe-other',writes=1,population='another team')
    assert collect(pilot(plan,arrivals([other_write],[])))==['Bail out! production write\n'], 'a different outcome population remains inside the pilot write guardrail'

@pytest.mark.skip('Part 5')
def test_goal_question_metric_trace():
    """GQM shares metric references and traces child goals without requiring both roles in each question."""
    ms=metrics();root=Goal('safe-diagnosis',(Question('speed',('speed',)),), (Goal('risk',(Question('read-only',('writes',)),Question('cost-shift',('workload','writes')))),))
    states={'speed':'pass','writes':'pass','workload':'fail'};before=copy.deepcopy(root)
    assert trace(root,ms,states)=={'status':'fail','questions':[(('safe-diagnosis','speed'),'pass'),(('safe-diagnosis','risk','read-only'),'pass'),(('safe-diagnosis','risk','cost-shift'),'fail')],'orphans':(),'issues':[]}, 'shared risk metrics and child goals retain every trace and the worst decision'
    bad=Goal('g',(Question('q',('speed','unknown')),Question('empty',())))
    result=trace(bad,ms,{'speed':'pass'})
    assert result=={'status':'ambiguous','questions':[(('g','q'),'ambiguous'),(('g','empty'),'ambiguous')],'orphans':('writes','workload'),'issues':['unknown:g/q:unknown','empty:g/empty','orphan:writes','orphan:workload','missing-kind:guardrail']}, 'orphans and bad links remain explicit rather than silently passing'
    assert trace(root,ms,{'speed':'pass','writes':'pass'})['status']=='ambiguous', 'an unmeasured counter is ambiguous rather than a passing leaf'
    assert root==before, 'trace evaluation cannot mutate the goal structure'
    with_orphan=trace(root,[*ms,replace(ms[2],name='unused')],states)
    assert with_orphan['status']=='fail' and with_orphan['issues']==['orphan:unused'], 'trace issues cannot downgrade an already failing measured result'
    with pytest.raises(ValueError):trace(root,ms,{'speed':'unknown'})
