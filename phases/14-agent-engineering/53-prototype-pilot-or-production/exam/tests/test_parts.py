import asyncio,copy,json,time
from dataclasses import replace
import pytest
from stagegate.stages import Marker,Registration,Decision,Session,CHANNELS,PILOT,required_controls,plan,audiences
from stagegate.registry import Registry
from stagegate.drift import Observation,drift
from stagegate.monitor import monitor,alert
from stagegate.dependencies import Component,Dependency,Deficit,responsibility_gaps

def markers(stage):return tuple(Marker(c,stage) for c in CHANNELS)
def record(key='system',stage='pilot',**kw):
    values=dict(id=key,declared_stage=stage,owner='platform',audience_cap=3,until='2026-11-05',authority=('read',),exit_criteria=('expand after evidence','revise unsafe workflow','stop on failed guardrail'),controls=required_controls(stage),markers=markers(stage));values.update(kw);return Registration(**values)
def observation(key='system',stage='pilot',**kw):
    values=dict(system=key,at='2026-11-05',exposed_users=3,production_data=True,write_authority=False,on_call=False,markers=markers(stage));values.update(kw);return Observation(**values)

@pytest.mark.skip('Part 1')
def test_deliberate_stage_plan():
    """Repair pilot obligations, missing-control reporting, declarations and active-audience telemetry."""
    pilot_decision=Decision(True,True,4,True,False);empty=record(controls=())
    assert plan(empty,pilot_decision)['missing_controls']==PILOT, 'the pilot plan includes its complete bounded learning responsibilities'
    equipped=record(controls=('rollback','audit'))
    assert plan(equipped,pilot_decision)['missing_controls']==tuple(c for c in PILOT if c not in equipped.controls), 'report missing controls rather than every required control'
    prod=record(stage='production');report=plan(prod,pilot_decision)
    assert report['declared_stage']=='production' and report['recommended_stage']=='pilot' and report['missing_controls']==(), 'readiness changes recommend review without silently downgrading a declaration'
    events=[Session('a','1','ana',True),Session('a','2','ana',True),Session('a','1','ana',False),Session('a','2','bo',True),Session('b','2','ana',True),Session('a','2','bo',False),Session('a','absent','unknown',False)]
    before=copy.deepcopy(events)
    assert audiences(events)==[('a',1),('a',1),('a',1),('a',1),('b',1),('a',0),('a',0)], 'active users require live-session references within each system'
    assert audiences([])==[] and events==before, 'telemetry leaves the original observations unchanged'
    events=[Session('pilot',str(i),f'user-{i}',True) for i in range(14000)]
    start=time.perf_counter();counts=audiences(events);elapsed=time.perf_counter()-start
    assert counts[0]==('pilot',1) and counts[-1]==('pilot',14000)
    assert elapsed<0.08, 'update active-audience cardinality without rebuilding the live-user set each time'

@pytest.mark.skip('Part 2')
def test_stage_registry_roundtrip(tmp_path):
    """Preserve declared responsibility and four independent markers rather than recomputing stage."""
    raw=' stop on unsafe write\n人工复核\r\n\t '
    item=record('team\'s α',stage='production',owner=' on-call α ',audience_cap=17,until='2027-01-03',authority=('read','write:bounded','read'),exit_criteria=(raw,'expand after 10 cases',''),markers=(Marker('configuration','production'),Marker('access','pilot'),Marker('telemetry',None),Marker('documentation','')))
    path=str(tmp_path/'registry.db');store=Registry(path);store.put(item);other=record('other');store.put(other);store.close();store=Registry(path)
    loaded=store.get(item.id)
    assert loaded==item and store.get('other')==other, 'the full declaration and each technical marker round-trip independently'
    assert type(loaded.audience_cap) is int and type(loaded.markers[0]) is Marker and type(loaded.authority) is tuple
    assert loaded.markers[2].value is None and loaded.markers[3].value=='', 'marker codec retains missing versus present empty values'
    changed=replace(item,declared_stage='pilot',controls=('audit','rollback'),exit_criteria=(raw,));store.put(changed);store.close();store=Registry(path)
    assert store.get(item.id)==changed and store.get('other')==other, 'explicit registration replacement affects only its named system'
    assert store.get(item.id) is not store.get(item.id), 'each read reconstructs an independent declaration'
    with pytest.raises(KeyError):store.get('missing')
    store.close()

@pytest.mark.skip('Part 3')
def test_stage_drift_observations():
    """Compare cumulative exposure and technical boundaries with an unchanged declaration."""
    pilot=record();safe=observation()
    assert drift(pilot,safe)==[], 'a bounded pilot may use production data through its inclusive final date'
    bad=replace(safe,exposed_users=4,at='2026-11-06',markers=(Marker('configuration','production'),Marker('documentation','pilot')))
    assert drift(pilot,bad)==['audience-overflow','pilot-expired','marker-mismatch:configuration','missing-marker:access','missing-marker:telemetry'], 'every boundary drift remains explicit in the fixed policy order'
    prototype=record(stage='prototype',owner='',controls=required_controls('prototype'))
    exposed=observation(stage='prototype',exposed_users=1,write_authority=True)
    assert drift(prototype,exposed)==['unowned-exposure','prototype-data','prototype-authority'], 'prototype exposure cannot acquire production data or authority by accident'
    production=record(stage='production');observed=observation(stage='production',on_call=False)
    assert drift(production,observed)==['production-on-call'], 'declared production retains its on-call responsibility despite missing operations'
    banner=replace(safe,markers=(Marker('documentation','pilot'),))
    assert drift(pilot,banner)==['missing-marker:configuration','missing-marker:access','missing-marker:telemetry'], 'a documentation banner alone is not an observable technical boundary'
    assert drift(replace(pilot,controls=tuple(c for c in PILOT if c!='rollback')),safe)==['missing-control:rollback'], 'claimed stage does not substitute for a required operational control'
    assert pilot.declared_stage=='pilot' and safe.exposed_users==3, 'observation never relabels the declaration or reduces admitted audience'
    assert drift(replace(pilot,owner=''),replace(safe,exposed_users=0))==['unowned-exposure'], 'data access needs an owner even before any users are admitted'
    unknown=tuple(Marker(c,'unclassified' if c=='telemetry' else 'pilot') for c in CHANNELS)
    assert drift(pilot,replace(safe,markers=unknown))==['missing-marker:telemetry'], 'an unknown finite marker is missing rather than another declared stage'

async def snapshots(rows,pulled):
    for row in rows:pulled.append(row);yield row

def collect(gen):
    async def run():return [x async for x in gen]
    return asyncio.run(run())

@pytest.mark.skip('Part 4')
def test_stage_drift_stream():
    """Drift episodes recover and rearm while unsafe snapshots never release another step."""
    a=record('a');b=record('b');safe=observation('a');unsafe=replace(safe,exposed_users=4,at='2026-11-06');again=replace(unsafe,at='2026-11-07');other=observation('b')
    rows=[unsafe,again,safe,unsafe,other];released=[];pulled=[]
    expected=[alert(a,unsafe,'audience-overflow'),alert(a,unsafe,'pilot-expired'),alert(a,unsafe,'audience-overflow'),alert(a,unsafe,'pilot-expired')]
    assert collect(monitor({'a':a,'b':b},snapshots(rows,pulled),released.append))==expected, 'recovery rearms all current reasons without duplicate alerts during one episode'
    assert released==[safe,other] and pulled==rows, 'already-alerted unsafe snapshots still block release while healthy systems continue'
    assert [json.loads(line.split(' - DRIFT - ',1)[1]) for line in expected][:2]==[{'system':'a','declared':'pilot','reason':'audience-overflow'},{'system':'a','declared':'pilot','reason':'pilot-expired'}]
    async def boundary():
        pulled=[];released=[];gen=monitor({'a':a},snapshots([unsafe,again],pulled),released.append)
        first=await gen.__anext__();second=await gen.__anext__()
        assert [first,second]==expected[:2] and pulled==[unsafe] and released==[], 'emit the complete current drift block before any future snapshot'
        await gen.aclose();assert pulled==[unsafe], 'closing after an alert cannot prefetch another exposure'
    asyncio.run(boundary())
    assert collect(monitor({'a':a},snapshots([],[]),released.append))==[]
    b_unsafe=replace(unsafe,system='b');released=[]
    separate=collect(monitor({'a':a,'b':b},snapshots([unsafe,b_unsafe],[]),released.append))
    assert separate==expected[:2]+[alert(b,b_unsafe,'audience-overflow'),alert(b,b_unsafe,'pilot-expired')] and released==[], 'the same reason starts a separate alert episode in another system'

@pytest.mark.skip('Part 5')
def test_necessary_component_responsibility():
    """Necessary edges carry concrete responsibility while optional isolated experiments remain legal."""
    components=[Component('root','service',('slo',),('read',)),Component('a','team-a',('rollback',),('read',)),Component('b','team-b',(),('read',)),Component('shared','',('audit',),('read','write')),Component('experiment','',(),('write',))]
    edges=[Dependency('root','b'),Dependency('root','a'),Dependency('a','shared',('audit',)),Dependency('b','shared',('recovery',)),Dependency('root','experiment',('rollback',),optional=True)]
    before=copy.deepcopy((components,edges))
    assert responsibility_gaps('root',components,edges)==[Deficit('shared','authority','write',('root','a','shared')),Deficit('shared','control','recovery',('root','b','shared')),Deficit('shared','owner','',('root','a','shared'))], 'shared components satisfy every necessary edge with the smallest real witness path'
    allowed=[replace(e,owner_required=False,allowed_authority=('read','write')) if e.child=='shared' else e for e in edges]
    assert responsibility_gaps('root',components,allowed)==[Deficit('shared','control','recovery',('root','b','shared'))], 'ownership and authority obligations are explicit per edge rather than inferred from a stage rank'
    assert responsibility_gaps('root',[replace(c,owner='') if c.id=='root' else c for c in components],[])==[Deficit('root','owner','',('root',))], 'ongoing responsibility begins with an owner for the root service'
    assert (components,edges)==before, 'dependency review cannot rewrite components or policy edges'
    with pytest.raises(ValueError):responsibility_gaps('root',components,[Dependency('root','missing')])
    chain=[Component(f'node-{i:04d}','team',(),('read',)) for i in range(1100)]
    links=[Dependency(chain[i].id,chain[i+1].id) for i in range(1099)]
    assert responsibility_gaps(chain[0].id,chain,links)==[], 'the supplied finite dependency helper handles long acyclic responsibility chains'
    with pytest.raises(ValueError,match='cycle'):
        responsibility_gaps('root',components,[Dependency('root','a'),Dependency('a','root')])
    optional_components=[*components,Component('unreached','',(),('write',))]
    optional_edges=[*edges,Dependency('experiment','unreached',('audit',))]
    assert responsibility_gaps('root',optional_components,optional_edges)==responsibility_gaps('root',components,edges), 'an optional-only subtree imposes no necessary responsibility on the root'
    pair=[Component('root','team',(),('read',)),Component('child','team',(),('read',))]
    assert responsibility_gaps('root',pair,[Dependency('root','child',('audit','rollback'))])==[Deficit('child','control','audit',('root','child')),Deficit('child','control','rollback',('root','child'))], 'each named control on a necessary edge is independently required'
