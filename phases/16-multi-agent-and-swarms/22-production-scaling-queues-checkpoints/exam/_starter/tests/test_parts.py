"""Five durable-execution tasks; each complete closure is tested after unlocking its Part."""
import asyncio
import csv
import io
from decimal import Decimal
from time import perf_counter
import pytest
from outboxflow.models import Checkpoint, Envelope, BurstReport, Intent, Receipt, StepPlan, DeployEvent, Message, Group
from outboxflow.primitives import CheckpointStore, AgentQueue, BurstMailbox
from outboxflow.service import resume_checkpoint, QueueDesk
from outboxflow.fixture import burst_fixture
from outboxflow.store import DurableArchive
from outboxflow.execution_support import AtomicReceiver, CrashCut, SimulatedCrash
from outboxflow.execution import commit_checkpoint_and_intent, dispatch_intents, recover_outbox
from outboxflow.wire_support import publish_events
from outboxflow.stream import project_deployment
from outboxflow.group_support import GroupCatalog, deliver_audit
from outboxflow.structure import audit_deployment

@pytest.mark.skip(reason='Part 1')
def test_part1_checkpoint_queue_and_complete_burst():
    """Choose the run numeric checkpoint and retain acknowledged FIFO correlation through the whole burst."""
    history=(Checkpoint('target',9,'v1',{'balance':9}),Checkpoint('target',10,'v1',{'balance':10}),Checkpoint('other',90,'v9',{'foreign':True}))
    index=CheckpointStore(history)
    assert resume_checkpoint(index,'target','balance')==10, 'resume consumes the numeric latest checkpoint belonging to its own run'
    assert index.latest('missing') is None, 'an absent run has no checkpoint'
    huge=10**40
    assert CheckpointStore((Checkpoint('h',huge,'v',{}),Checkpoint('h',huge+1,'v',{}))).latest('h').step==huge+1, 'exact numeric supersteps are not lexicographic or binary64 keys'
    a,b=Envelope('a','run',2,'one'),Envelope('b','run',3,'two');q=AgentQueue();q.enqueue(a);q.step();assert q.state=='processing' and q.response is None
    q.step();q.enqueue(b);assert q.state=='response' and q.response==a
    q.step();assert q.state=='response' and q.response==a, 'new queued input cannot consume an unacknowledged response'
    with pytest.raises(ValueError,match='pending input'):q.acknowledge('b')
    assert q.response==a and q.state=='response', 'an unrelated acknowledgement cannot release pending input'
    q.acknowledge('a');q.step();q.step();assert q.response==b and q.state=='response', 'each response belongs to the actual next dequeued input'
    q.acknowledge('b');q.step();assert q.state=='idle' and q.response is None, 'acknowledged response is cleared before idle queue polling'
    mailbox=BurstMailbox((a,b));assert mailbox.drain()==(a,b) and mailbox.drain()==(), 'a complete burst drains exactly its FIFO inputs once'
    messages,expected=burst_fixture();start=perf_counter();report=QueueDesk().drain_burst(messages)
    assert report==expected, 'complete burst output retains every actual input, own run count and signed amount'
    elapsed=perf_counter()-start
    assert elapsed<0.10, 'complete FIFO burst stays within the declared local batch budget'

@pytest.mark.skip(reason='Part 2')
def test_part2_transaction_aware_domain_records(tmp_path):
    """Reopen exact checkpoint, intent and actual receipt associations without committing outside the caller scope."""
    p=tmp_path/'archive.db';a=DurableArchive(p);step=10**35+10
    c1=Checkpoint('run,α',step,'old-runtime',{'functions':['invoke',False,1,None],'nested':{'x':[2,3]}});c2=Checkpoint('peer',step+1,'v2',{'other':9})
    i1=Intent(c1.run,step,'effect-1',Decimal('9007199254740993.0100'),'group/a',{'kind':'leaf','ok':False});i2=Intent(c2.run,step+1,'effect-1',Decimal('0.000'),'group/b',{'result':[1,True]})
    r1=Receipt(i1.key,'receiver-old',i1.amount,{'destination':i1.destination,'payload':i1.payload})
    with a.atomic():
        a.write_checkpoint(c1);a.write_checkpoint(c2);a.write_intent(i1);a.write_intent(i2);a.acknowledge(r1)
    a.close();a=DurableArchive(p)
    assert a.checkpoints()==(c1,c2) and a.intents()==(i1,i2) and a.receipts()==(r1,), 'SQLite reopen retains every own checkpoint runtime state, intent field and actual receipt'
    assert a.intents()[0].amount.as_tuple()==i1.amount.as_tuple(), 'synthetic Decimal charge scale and large coefficient remain exact'
    assert a.pending(c1.run)==() and a.pending(c2.run)==(i2,), 'pending intent association uses the full run step effect key and stored receipt'
    with a.atomic():a.write_checkpoint(c1);a.write_intent(i1);a.acknowledge(r1)
    assert len(a.checkpoints())==2 and len(a.intents())==2 and len(a.receipts())==1, 'identical immutable record replay retains one original durable record'
    rolled=Checkpoint('rollback',4,'v3',{'counter':4})
    with pytest.raises(RuntimeError,match='rollback'):
        with a.atomic():a.write_checkpoint(rolled);raise RuntimeError('rollback')
    a.close();a=DurableArchive(p);assert rolled not in a.checkpoints(), 'record projection respects the caller transaction rollback boundary'
    with pytest.raises(ValueError,match='conflicting'):
        with a.atomic():a.write_checkpoint(Checkpoint(c1.run,step,'replacement-runtime',{}))
    assert a.checkpoints()[0]==c1, 'conflicting replay cannot replace the original durable runtime or state'
    a.close()

    shared_step=(Checkpoint('collision-a',4,'v1',{'own':'a'}),Checkpoint('collision-b',4,'v2',{'own':'b'}))
    pair=DurableArchive(tmp_path/'same-step.db')
    with pair.atomic():
        for checkpoint in shared_step:pair.write_checkpoint(checkpoint)
    pair.close();pair=DurableArchive(tmp_path/'same-step.db')
    assert pair.checkpoints()==shared_step, 'distinct runs retain independent checkpoints at the same numeric superstep'
    pair.close()


@pytest.mark.skip(reason='Part 3')
def test_part3_atomic_commit_dispatch_and_recovery(tmp_path):
    """Compose durable records atomically, independently deliver stable keys, and recover committed pending work at four crash cuts."""
    plans=tuple(StepPlan(Checkpoint('run',s,'v1',{'counter':s}),Intent('run',s,'charge',Decimal('1.2500'),'sink',{'step':s}))for s in(0,9,10))
    uncommitted=DurableArchive(tmp_path/'uncommitted.db');external=AtomicReceiver(tmp_path/'uncommittedReceiver.db')
    with pytest.raises(ValueError,match='committed sender records'):
        with uncommitted.atomic():
            uncommitted.write_intent(plans[0].intent)
            dispatch_intents(uncommitted,external,'run')
    assert uncommitted.intents()==() and external.effects()==(), 'an open sender transaction cannot admit an independent external effect before commit'
    uncommitted.close();external.close()
    for cut in('after_checkpoint','before_commit','after_commit','after_send'):
        p=tmp_path/(cut+'sender.db');rp=tmp_path/(cut+'receiver.db');a=DurableArchive(p);r=AtomicReceiver(rp);crash=CrashCut(cut)
        with pytest.raises(SimulatedCrash,match=cut):recover_outbox(a,r,'run',plans,crash)
        if cut in('after_checkpoint','before_commit'):
            assert a.checkpoints()==() and a.intents()==() and r.effects()==(), 'uncommitted checkpoint and intent roll back together before any receiver effect'
        else:
            assert a.checkpoints()==(plans[0].checkpoint,) and a.intents()==(plans[0].intent,), 'committed intent survives the crash independently of delivery acknowledgement'
        if cut=='after_send':assert len(r.effects())==1 and a.receipts()==(), 'the independent receiver can commit an effect before the sender acknowledgement exists'
        a.close();r.close();a=DurableArchive(p);r=AtomicReceiver(rp);report=recover_outbox(a,r,'run',plans)
        assert report.checkpoint==plans[-1].checkpoint and report.intents==tuple(p.intent for p in plans), 'recovery resumes the original run numeric checkpoint and commits every missing plan'
        assert report.receipts==r.effects() and len(r.effects())==3 and sum(x.amount for x in r.effects())==Decimal('3.7500'), 'stable receiver keys make repeated delivery one effective charge under the explicit atomic receiver contract'
        assert a.pending('run')==() and all(x.key==p.intent.key for x,p in zip(report.receipts,plans)), 'every committed intent receives its own actual delivery receipt'
        again=recover_outbox(a,r,'run',plans);assert again==report and len(r.effects())==3, 'completed recovery is stable without replaying a fresh effective charge'
        a.close();r.close()
    a=DurableArchive(tmp_path/'terminal.db');r=AtomicReceiver(tmp_path/'terminalreceiver.db')
    commit_checkpoint_and_intent(a,plans[-1]);a.close();a=DurableArchive(tmp_path/'terminal.db');report=recover_outbox(a,r,'run',plans)
    assert report.checkpoint==plans[-1].checkpoint and report.receipts==r.effects() and len(r.effects())==1, 'terminal checkpoint still drains its committed pending intent before skipping earlier plans'
    a.close();r.close()

    shared=DurableArchive(tmp_path/'shared-sender.db');shared_receiver=AtomicReceiver(tmp_path/'shared-receiver.db')
    foreign=StepPlan(Checkpoint('foreign',99,'v2',{'counter':99}),Intent('foreign',99,'charge',Decimal('2.000'),'elsewhere',{'foreign':True}))
    commit_checkpoint_and_intent(shared,foreign);dispatch_intents(shared,shared_receiver,'foreign')
    own_report=recover_outbox(shared,shared_receiver,'run',(plans[0],))
    assert own_report.receipts==tuple(receipt for receipt in shared_receiver.effects() if receipt.key[0]=='run') and len(own_report.receipts)==1 and len(shared.receipts())==len(shared_receiver.effects())==2, 'recovery reports only its own run receipts while retaining independent foreign delivery evidence'
    shared.close();shared_receiver.close()


@pytest.mark.skip(reason='Part 4')
def test_part4_rainbow_actual_bindings_csv():
    """Publish original runtime bindings and own-version active counts through successful and failed resumes."""
    events=tuple(DeployEvent(*row)for row in(('deploy','','v1'),('start','old','v1'),('deploy','','v2'),('start','new','v2'),('resume','old','v2'),('failed_resume','old','v2'),('retire','','v1'),('finish','old','v2'),('retire','','v1'),('resume','new','v1'),('finish','new','v1'),('retire','','v2')))
    rows=list(csv.DictReader(io.StringIO(asyncio.run(publish_events(events,project_deployment)))))
    assert tuple(rows[0])==('event','thread_id','runtime_version','active_count','retire_allowed') and len(rows)==len(events), 'every actual deployment event has one complete parsed CSV row'
    assert [(rows[k]['runtime_version'],rows[k]['active_count'])for k in(1,3)]==[('v1','1'),('v2','1')], 'new runs follow each declared deployment choice'
    assert [(rows[k]['thread_id'],rows[k]['runtime_version'],rows[k]['active_count'])for k in(4,5)]==[('old','v1','1'),('old','v1','1')], 'successful and failed resume both retain the original in-flight runtime binding'
    assert rows[6]['retire_allowed']=='False' and rows[8]['retire_allowed']=='True', 'a runtime may retire only after its actual active runs drain'
    assert rows[7]['runtime_version']=='v1' and rows[7]['active_count']=='0' and rows[9]['runtime_version']=='v2', 'finish and later resume report each run own preserved version'
    assert rows[-1]['runtime_version']=='v2' and rows[-1]['active_count']=='0' and rows[-1]['retire_allowed']=='True'

@pytest.mark.skip(reason='Part 5')
def test_part5_nested_admin_routes_and_run_outputs(tmp_path):
    """Build admin ladders and nested declared exports over complete Given scoped address and mailbox binding."""
    run='run-1';source='root/a/deep/worker';dest='root/b/worker';hops=(source,'root/a/deep/admin','root/a/admin','root/admin','root/b/admin',dest)
    envelope=Envelope('good',run,4,'actual-route');assert QueueDesk().drain_burst((envelope,)).delivered==(envelope,)
    payload={'source':source,'hops':list(hops),'kind':'leaf','body':{'answer':envelope.body}}
    plan=StepPlan(Checkpoint(run,0,'v-original',{'message':envelope.uid}),Intent(run,0,envelope.uid,Decimal('2.00'),dest,payload));a=DurableArchive(tmp_path/'route.db');r=AtomicReceiver(tmp_path/'routeReceiver.db');report=recover_outbox(a,r,run,(plan,));a.close();a=DurableArchive(tmp_path/'route.db');receipt=a.receipts()[0];body=receipt.result['payload'];good=Message(receipt.key[2],receipt.key[0],body['source'],receipt.result['destination'],tuple(body['hops']),body['kind'],body['body']);a.close();r.close()
    bypass=Message('bypass',run,source,dest,(source,dest),'leaf',{});other=Message('other','run-2',source,dest,hops,'leaf',{});unexported=Message('hidden',run,source,dest,hops,'leaf',{})
    local=Message('local',run,'root/a/worker','root/a/peer',('root/a/worker','root/a/peer'),'leaf',{});fake=Message('fake',run,'root/a/admin','root/a/worker',('root/a/admin','root/a/worker'),'leaf',{})
    deep=Group('deep','root/a/deep/admin',(source,),messages=('good','bypass','other','hidden'),exports=('good','bypass','other','hidden'))
    ga=Group('a','root/a/admin',('root/a/worker','root/a/peer'),(deep,),('local','fake'),('good','bypass','other'))
    gb=Group('b','root/b/admin',(dest,));root=Group('root','root/admin',(),(ga,gb));catalog=GroupCatalog(root,(good,bypass,other,unexported,local,fake));audit=audit_deployment(catalog,run)
    assert catalog.local('a','worker')!=catalog.local('b','worker'), 'complete Given scoped endpoint binding preserves same local name independent mailboxes'
    ar,br=audit.children;dr=ar.children[0];routes={x.uid:x for x in dr.own}
    assert audit.uid=='root' and ar.path==('root','a') and dr.path==('root','a','deep') and br.path==('root','b'), 'every nested group retains its actual structural audit'
    assert routes['good'].accepted and routes['good'].expected_hops==hops and not routes['bypass'].accepted, 'cross-group leaf traffic follows the complete up and down admin ladder'
    assert 'admin-route' in routes['bypass'].reasons and 'undeclared-export:a' in routes['hidden'].reasons, 'an intermediate admin or group export permission cannot be bypassed'
    assert tuple(m.uid for m in ar.outputs)==('good',) and tuple(m.uid for m in dr.outputs)==('good',), 'declared cross-group outputs include only route-valid messages of the actual requested run'
    assert ar.own[0].accepted and not ar.own[1].accepted and ar.own[1].reasons==('origin',), 'same-group route remains direct while complete Given origin intake rejects an admin impersonating leaf output'
    assert audit.outputs==() and br.outputs==(), 'local or inbound messages do not become undeclared cross-group outputs'
    deliver_audit(catalog,audit,run)
    assert catalog.mailboxes[dest]==[good] and catalog.mailboxes[catalog.local('a','worker')]==[] and catalog.mailboxes['root/a/peer']==[local], 'complete Given delivery binds accepted actual-run messages to distinct scoped mailboxes'

    self_message=Message('self',run,'solo/worker','solo/worker',('solo/worker',),'leaf',{})
    self_audit=audit_deployment(GroupCatalog(Group('solo','solo/admin',('solo/worker',),messages=('self',)),(self_message,)),run)
    assert self_audit.own[0].accepted and self_audit.own[0].expected_hops==('solo/worker',), 'self delivery uses its one actual endpoint without inventing a duplicate hop'
    assert tuple(row.uid for row in dr.own)==('good','bypass','other','hidden') and routes['other'].run=='run-2' and routes['other'].accepted, 'each owning group retains every declared route observation independently of requested-run outputs'
    unrelated_b=Group('b','root/b/admin',(dest,),exports=('local',))
    unrelated=audit_deployment(GroupCatalog(Group('root','root/admin',(),(ga,unrelated_b)),tuple(catalog.messages.values())),run)
    assert unrelated.children[1].outputs==() and unrelated.children[0].own[0].accepted, 'an export declaration cannot claim accepted traffic sourced outside the group subtree'
