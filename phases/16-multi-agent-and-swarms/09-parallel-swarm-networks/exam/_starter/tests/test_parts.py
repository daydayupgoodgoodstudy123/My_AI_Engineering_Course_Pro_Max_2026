"""Five sequential tasks in a deterministic local pull-worker desk.

Part1: result identity, producer closure and stable event-calendar performance.
Part2: exact framed journal and observed task lifecycle replay.
Part3: ready specialist admission, enqueue aging and independent simultaneous claims.
Part4: domain event data through the complete supplied byte-frame driver.
Part5: nested topic constraints, pool boundaries and actual leaf completion counts.
"""
import asyncio,json,struct,time
from dataclasses import replace
import pytest

@pytest.mark.skip('Part 1')
def test_complete_fifo_replay():
    """Every task retains its actual completion while the producer and event calendar drain."""
    from workpull.models import Task,Worker
    from workpull.runtime import CompletionDesk
    from workpull.fixture import completion_fixture
    from workpull.support import execute_task
    workers=(Worker('worker一',('data',)),)
    tasks=(Task('first','data','one',0,2,pre_assigned='other-worker'),Task('second','data','two',0,1,pre_assigned='other-worker'))
    result=CompletionDesk().run(tasks,workers)
    assert tuple((c.task_id,c.worker_uid,c.start_us,c.finish_us)for c in result.completions)==(('first','worker一',0,2),('second','worker一',2,3)) and tuple(card[0]for card in result.cards)==('first','second'), 'each task keeps its own result and actual completing worker across repeated worker use'
    assert tuple(card[-1]for card in result.cards)==tuple(execute_task(t,workers[0])for t in tasks) and result.counts==(('worker一',2),), 'complete payload results and real per-worker counts remain independently observable'
    gap=(tasks[0],Task('late','data','零',10,0))
    later=CompletionDesk().run(gap,workers)
    assert tuple(c.task_id for c in later.completions)==('first','late') and later.unfinished==() and later.finished_us==10, 'an empty ready queue does not close a producer with future arrivals'
    assert later.completions[-1].start_us==later.completions[-1].finish_us==10 and later.counts==(('worker一',2),), 'zero-duration work still produces one real observation and completion count through the supplied driver'
    parallel=(Worker('left',('data',)),Worker('right',('data',)),Worker('idle',('data',)))
    pair=CompletionDesk().run(tasks,parallel)
    assert tuple((c.task_id,c.worker_uid,c.finish_us)for c in pair.completions)==(('second','right',1),('first','left',2)) and pair.counts==(('left',1),('right',1),('idle',0)), 'completion order follows real logical finish times and includes idle workers separately'
    seen=[]
    def observed(task,worker):seen.append((task.task_id,worker.uid));return task.payload+'!'
    calls=CompletionDesk().run(tasks,workers,observed)
    assert seen==[('first','worker一'),('second','worker一')] and tuple(c.value for c in calls.completions)==('one!','two!'), 'the local worker callback executes every declared payload once and its own result reaches the receipt'
    args,expected=completion_fixture();started=time.perf_counter();complete=CompletionDesk().run(*args)
    assert complete==expected, 'the complete task replay retains every input trace actual result worker count and receipt field'
    elapsed=time.perf_counter()-started
    assert elapsed<0.14, 'complete variable-duration task replay remains responsive'

@pytest.mark.skip('Part 2')
def test_append_task_lifecycle_journal(tmp_path):
    """Reopening follows recorded task lifecycle and actual workers rather than arrival metadata."""
    from workpull.models import Task,Worker,Lifecycle,TraceArchive
    from workpull.journal import TaskJournal
    huge=2**60+17
    tasks=(Task('later一','text','原文\r\n',huge+10,0,5,'fixed-wrong'),Task('early','image','pixels',huge,3,-2))
    workers=(Worker('actual一',('text','image')),)
    first=(Lifecycle('arrival','early',huge,priority=-2),Lifecycle('pull','early',huge,'actual一',huge,huge+3,priority=-2))
    path=tmp_path/'trace.wpj';journal=TaskJournal(path);journal.append(tasks,workers,first)
    assert TaskJournal(path).load()==TraceArchive(tasks,workers,first), 'reopening retains declared task order and recorded observations independently of arrival times'
    assert TaskJournal(path).task_states()==(('later一','not-arrived',None,None,None,None),('early','running','actual一',huge,None,None)), 'a pulled task remains running and a future declaration is not a completed result'
    tail=(Lifecycle('completion','early',huge+3,'actual一',huge,huge+3,'actual output'),Lifecycle('arrival','later一',huge+10,priority=5))
    journal.append(events=tail);reopened=TaskJournal(path)
    assert reopened.load()==TraceArchive(tasks,workers,first+tail) and reopened.task_states()==(('later一','ready',None,None,None,None),('early','complete','actual一',huge,huge+3,'actual output')), 'appended completion evidence supplies actual assignment result and phase without completing an arrival'
    assert reopened.load().tasks[0].duration_us==0 and type(reopened.load().trace[-1].time_us)is int and reopened.load().trace[-1].time_us==huge+10, 'the supplied signed-integer and UTF8 codec retains exact task times and source payloads'
    broken=tmp_path/'partial.wpj';broken.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError,match='partial journal frame'):TaskJournal(broken).load()

    repeated=(Task('copy-a','text','same payload',5,1),Task('copy-b','text','same payload',0,2))
    repeated_path=tmp_path/'same-payload.wpj';TaskJournal(repeated_path).append(repeated,workers)
    assert TaskJournal(repeated_path).load().tasks==repeated, 'equal payloads retain distinct declared task identities'

@pytest.mark.skip('Part 3')
def test_specialist_aging_pull_claims(tmp_path):
    """Ready specialist workers pull aged work once with stable declared tie order."""
    from workpull.models import Task,Worker
    from workpull.runtime import CompletionDesk
    from workpull.journal import TaskJournal
    from workpull.scheduling import eligible_ready_tasks,effective_priority,claim_free_workers
    old=Task('old','text','old',0,1,0);recent=Task('recent','text','new',18,1,3);future=Task('future','text','later',30,1,100);image=Task('image','image','img',0,1,100)
    specialist=Worker('text-worker',('text',));ready=(image,recent,old,future)
    assert eligible_ready_tasks(20,ready,specialist)==(recent,old), 'topic admission and actual arrival precede priority comparison'
    assert effective_priority(old,20,5)==4 and effective_priority(recent,20,5)==3, 'waiting priority grows from enqueue time at the actual pull instant'
    with pytest.raises(ValueError,match='not arrived'):effective_priority(future,20,5)
    order={t.task_id:i for i,t in enumerate((old,recent,future,image))}
    assert claim_free_workers(20,ready,(specialist,),order,5)==((specialist,old),), 'an aged eligible task outranks recent work without choosing an ineligible or future task'
    tie=replace(recent,task_id='tie',arrival_us=0,priority=0);second=Worker('second-text',('text',));declared={'tie':0,'old':1}
    claimed=claim_free_workers(20,(old,tie),(specialist,second),declared,5)
    assert claimed==((specialist,tie),(second,old)), 'simultaneous free workers claim each task once using original task sequence for score ties'
    tasks=(Task('long','text','long',0,10),Task('waiting','text','wait',1,0),Task('fresh','text','fresh',10,1,2),Task('unserved','image','x',0,0,100))
    workers=(specialist,)
    source=tmp_path/'arrivals.wpj';TaskJournal(source).append(tasks,workers)
    saved=TaskJournal(source).load();run=CompletionDesk().run(saved.tasks,saved.workers,selector=claim_free_workers,aging_interval=2)
    assert tuple((c.task_id,c.start_us,c.finish_us)for c in run.completions)==(('long',0,10),('waiting',10,10),('fresh',10,11)) and run.unfinished==('unserved',), 'running work is not preempted and enqueue aging applies before each later specialist pull'
    assert run.counts==((specialist.uid,3),) and tuple(e.task_id for e in run.trace if e.kind=='pull')==('long','waiting','fresh'), 'each admitted task has exactly one actual pull and actual worker completion'
    both=(Worker('image-worker',('image',)),specialist)
    assigned=claim_free_workers(0,(old,image),both,{'old':0,'image':1},5)
    assert assigned==((both[0],image),(specialist,old)), 'each free worker applies its own topic subscriptions during the same claim batch'

    fractional=Task('fractional','text','partial wait',10,1,-2)
    assert effective_priority(fractional,13,5)==-2 and effective_priority(fractional,15,5)==-1, 'partial waiting intervals do not earn priority early'

@pytest.mark.skip('Part 4')
def test_observed_event_frames():
    """Length frames carry actual task lifecycle fields while the complete driver owns transport."""
    from workpull.models import Task,Worker
    from workpull.runtime import CompletionDesk
    from workpull.stream import EventProjection
    from workpull.wire_support import encode_events
    tasks=(Task('任务一','text','你好',7,0,4,'wrong-fixed'),Task('second','text','other',7,2,1))
    report=CompletionDesk().run(tasks,(Worker('actual一',('text',)),));events=report.trace
    class Source:
        def __init__(self):self.i=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.i==len(events):raise StopAsyncIteration
            event=events[self.i];self.i+=1;return event
        async def aclose(self):self.closed+=1
    async def collect():
        source=Source();stream=encode_events(source,EventProjection());chunks=[await anext(stream)]
        assert source.i==1, 'the supplied frame driver publishes the current recorded event before pulling another'
        async for chunk in stream:chunks.append(chunk)
        assert source.closed==1, 'the supplied event driver closes its source once'
        return b''.join(chunks)
    raw=asyncio.run(collect());pos=0;rows=[]
    while pos<len(raw):
        size=struct.unpack_from('>I',raw,pos)[0];pos+=4
        assert pos+size<=len(raw), 'the supplied frame header counts actual encoded payload bytes'
        rows.append(json.loads(raw[pos:pos+size]));pos+=size
    assert pos==len(raw) and len(rows)==len(events) and tuple(r['kind']for r in rows)==tuple(e.kind for e in events), 'every real observation retains its phase in recorded event order'
    arrivals=[r for r in rows if r['kind']=='arrival'];pulls=[r for r in rows if r['kind']=='pull'];done=[r for r in rows if r['kind']=='completion']
    assert arrivals==[{'kind':'arrival','task_id':t.task_id,'time_us':7,'queued_priority':t.priority}for t in tasks], 'arrival evidence retains queued priority without inventing assignment or result'
    assert pulls==[{'kind':'pull','task_id':'任务一','time_us':7,'worker_uid':'actual一','start_us':7,'finish_us':7},{'kind':'pull','task_id':'second','time_us':7,'worker_uid':'actual一','start_us':7,'finish_us':9}], 'pull evidence retains actual worker start and finish independently of the fixed-assignment hint'
    assert tuple((r['task_id'],r['time_us'],r['worker_uid'],r['result'])for r in done)==tuple((c.task_id,c.finish_us,c.worker_uid,c.value)for c in report.completions), 'completion frames retain their own actual result and finish instant'

    low=CompletionDesk().run((Task('low','text','negative priority',0,1,-3),),(Worker('priority-worker',('text',)),))
    assert EventProjection().event_payload(low.trace[0])=={'kind':'arrival','task_id':'low','time_us':0,'queued_priority':-3}, 'arrival evidence preserves the observed signed queued priority'

@pytest.mark.skip('Part 5')
def test_nested_swarm_pool_contracts():
    """Nested groups narrow topics, inherit only visible pools and total actual completed workers."""
    from workpull.models import Group,Pool,Worker,Task
    from workpull.deployment_support import GroupCatalog
    from workpull.deployment import inspect_deployment
    from workpull.runtime import CompletionDesk
    from workpull.scheduling import claim_free_workers
    east=Group('east',('text','image'),(Pool('private'),),(Worker('same',('text','image','audio')),))
    west=Group('west',('image',),(Pool('private'),),(Worker('same',('text','image')),))
    root=Group('mesh',('text','image'),(Pool('common',True),Pool('root-private')),(Worker('admin',('text',)),),(east,west))
    catalog=GroupCatalog(root);east_uid=catalog.full_worker_uid(('mesh','east'),'same');west_uid=catalog.full_worker_uid(('mesh','west'),'same')
    workers=(Worker(east_uid,('text','image')),Worker(west_uid,('image',)))
    tasks=(Task('t0','text','one',0,1),Task('t1','text','two',0,2),Task('i0','image','image',0,0),Task('pending','audio','not admitted',0,1))
    run=CompletionDesk().run(tasks,workers,selector=claim_free_workers,aging_interval=2);tree=inspect_deployment(root,run.completions);left,right=tree['children']
    assert left['workers'][0][0]==east_uid and right['workers'][0][0]==west_uid, 'the supplied full-path catalog keeps group-local worker declarations independent'
    assert left['workers'][0][1]==('text','image') and right['workers'][0][1]==('image',), 'effective subscriptions are the intersection of every enclosing group scope and the worker topics'
    pools={tuple(owner)+(p.pool_id,):uid for owner,uid,p in catalog.all_pools()}
    assert left['workers'][0][2]==(pools[('mesh','common')],pools[('mesh','east','private')]) and right['workers'][0][2]==(pools[('mesh','common')],pools[('mesh','west','private')]), 'a worker sees its own pools and shared ancestor pools without sibling or ancestor private pools'
    assert tree['completed']==3 and left['completed']==2 and right['completed']==1 and left['workers'][0][3]==2 and right['workers'][0][3]==1 and run.unfinished==('pending',), 'group totals use actual leaf completions and exclude queued or unserved work'
    narrowed=replace(root,topics=('text',));closed=inspect_deployment(narrowed,())
    assert closed['children'][1]['workers'][0][1]==() and closed['children'][1]['completed']==0, 'an enclosing topic restriction can leave a specialist with no admissible topic or completed work'
    empty_scope=inspect_deployment(replace(root,topics=()),())
    assert empty_scope['workers'][0][1]==() and all(row[1]==()for child in empty_scope['children']for row in child['workers']), 'an explicit empty enclosing restriction admits no topics'
    with_sibling_shared=replace(root,children=(east,replace(west,pools=west.pools+(Pool('branch-only',True),))))
    branch_view=inspect_deployment(with_sibling_shared,())
    assert branch_view['children'][0]['workers'][0][2]==left['workers'][0][2], 'shared pools remain inside their owning ancestor branch'
