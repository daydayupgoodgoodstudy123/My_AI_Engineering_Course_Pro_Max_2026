"""Five locked local routine-handoff exercises; no LLM or real refund is invoked."""
import asyncio,json,time
import pytest
from routinehop.models import Agent,Tool,ToolCall,AskForOrder,ReadyRefund,CallResult,Transfer,CallSkipped,CallFailed,Reply,Continuation,TransferRequest,Note,ToolFailure,AgentReturn,DataReturn
from routinehop.support import RoutineCatalog,origin_card
from routinehop.service import IntakeDesk,ReplayDesk
from routinehop.fixture import replay_fixture
from routinehop.store import RoutineStore
from routinehop.batch import bind_batch_owner,interpret_raw_tool_return,run_batch
from routinehop.stream import ReceiptProjection
from routinehop.wire_support import publish_receipts

def tools_fixture():
    effects=[];holder={}
    def data_a(value='A-data'):
        effects.append(('A',value));return value
    def data_b(value='B-data'):
        effects.append(('B',value));return value
    def transfer():
        effects.append(('A','transfer'));return holder['B']
    def agent_like():return{'name':'B','instructions':'ordinary data','functions':[]}
    def fail():raise ToolFailure('declared-local-failure')
    a=Agent('A','triage',(Tool('same',data_a),Tool('handoff',transfer),Tool('description',agent_like),Tool('fail',fail),Tool('removed',lambda:Agent('removed','no live tools'))))
    def transfer_back():
        effects.append(('B','transfer'));return holder['A']
    b=Agent('B','refund',(Tool('same',data_b),Tool('handoff',transfer_back)))
    holder['A']=a;holder['B']=b
    return RoutineCatalog((a,b)),effects

@pytest.mark.skip('Part 1')
def test_refund_receipt_and_last_k_guard():
    """Repair opaque refund intake, outgoing transfer receipts and the online last-three handoff guard."""
    desk=IntakeDesk({'00077':'leading-zero-order','42':'real-but-unrequested-order'})
    assert desk.refund('Please refund order 00077')==('00077','leading-zero-order'),'opaque order identifiers select their exact local receipt'
    assert isinstance(desk.refund('I need a refund'),AskForOrder)and desk.refund_calls==['00077'],'missing order information asks before any refund invocation'
    from routinehop.intake import make_transfer_receipt
    assert origin_card(make_transfer_receipt('h1','triage','refund'))==('h1','triage','refund'),'handoff receipts identify the outgoing routine'
    observations,expected=replay_fixture()
    started=time.perf_counter()
    report=ReplayDesk().replay('perf',observations)
    assert report==expected,'complete replay retains every observation receipt and loop decision'
    elapsed=time.perf_counter()-started
    assert elapsed<0.075,'complete typed handoff replay remains responsive'
    assert len(report.audit)==len(observations)and len(report.receipts)==8103,'the complete independent audit remains available after loop exit'
    mixed=(TransferRequest('a','A','B'),Note('B','ordinary note'),TransferRequest('b','B','A'),Note('A','another note'),TransferRequest('c','A','B'),TransferRequest('d','B','C'))
    result=ReplayDesk().replay('mixed',mixed)
    assert result.first_stop==4 and result.stopped==(False,False,False,False,True,True),'only typed handoffs consume ring slots and an exit stays active'
    triangle=(TransferRequest('a','A','B'),TransferRequest('b','B','C'),TransferRequest('c','C','A'),TransferRequest('d','A','A'))
    assert ReplayDesk().replay('triangle',triangle).first_stop is None,'a three-routine route and a self edge are not a two-routine loop'
    assert ReplayDesk().replay('independent',mixed[:1]).stopped==(False,),'each caller run begins with an independent loop guard'
    assert IntakeDesk({'0':'zero'}).refund('order 0')==('0','zero'),'an explicit zero order is a real opaque identifier'

@pytest.mark.skip('Part 2')
def test_caller_snapshot_and_runtime_rebinding(tmp_path):
    """Persist complete caller continuation and rebind the active routine from the new runtime catalog."""
    catalog,_=tools_fixture();a=catalog.agent('A');b=catalog.agent('B')
    history=(CallResult('d','A','same',{'amount':2**70+3,'empty':'','null':None,'unicode':'退\n款','functions':['function','invoke']}),Transfer('h','A','handoff','B'),CallSkipped('s','A','same'),CallFailed('f','B','same','local'),Reply('B',''))
    snapshot=Continuation('caller/one',b,history,(2**70+1,0,2**70+2))
    store=RoutineStore(tmp_path);store.save(snapshot);store.save(Continuation('caller/two',a,(Reply('A','second'),),(7,)))
    fresh_catalog,fresh_effects=tools_fixture();reopened=RoutineStore(tmp_path).load('caller/one',fresh_catalog)
    assert reopened==Continuation('caller/one',fresh_catalog.agent('B'),history,snapshot.request_ids),'reopening retains complete ordered caller observations and active routine identity'
    assert reopened.active is fresh_catalog.agent('B')and reopened.active is not b,'runtime callables are rebound from the supplied current catalog'
    assert fresh_catalog.function(reopened.active,'same').invoke()=='B-data'and fresh_effects==[('B','B-data')],'the rebound active routine exposes its own callable namespace'
    assert RoutineStore(tmp_path).load('caller/two',fresh_catalog).history==(Reply('A','second'),),'saving one caller preserves another caller continuation'
    replacement=Continuation('caller/one',fresh_catalog.agent('A'),(Reply('A','resumed'),),(9,));store.save(replacement)
    assert RoutineStore(tmp_path).load('caller/one',fresh_catalog)==replacement,'a caller snapshot represents the complete declared continuation'
    documents=[json.loads(p.read_text())for p in tmp_path.glob('*.json')]
    assert all(set(d)=={'session','active','history','request_ids'}and type(d['active'])is str and d['active']in('A','B')for d in documents),'snapshot documents persist the declared caller schema and active routine name'
    assert reopened.history[0].value['functions']==['function','invoke'],'ordinary tool data may contain callable-related words without becoming runtime definitions'

    repeated=Reply('A','  repeated\n收据  ')
    repeated_history=(repeated,CallResult('middle','A','same',{'value':None}),repeated,repeated)
    duplicate_snapshot=Continuation('caller/repeated',fresh_catalog.agent('A'),repeated_history,(0,0,9))
    store.save(duplicate_snapshot)
    assert RoutineStore(tmp_path).load('caller/repeated',fresh_catalog)==duplicate_snapshot,'repeated caller receipts retain their occurrence order'

@pytest.mark.skip('Part 3')
def test_owner_bound_batch_control_returns():
    """Bind original batch tools, distinguish Agent-valued control and skip all transfer-tail effects."""
    catalog,effects=tools_fixture();a=catalog.agent('A');b=catalog.agent('B')
    calls=(ToolCall('before','same'),ToolCall('switch','handoff'),ToolCall('tail','same',( ('value','forbidden-tail'),)))
    bound=bind_batch_owner(a,calls,catalog)
    assert tuple((x.owner.name,x.function is catalog.function(a,x.call.tool))for x in bound)==(('A',True),('A',True),('A',True)),'every batch function is bound to the original routine before invocation'
    report=run_batch(a,calls,catalog)
    assert report.active is b and report.receipts==(CallResult('before','A','same','A-data'),Transfer('switch','A','handoff','B'),CallSkipped('tail','A','same')),'the first genuine Agent return transfers control and preserves explicit tail skips'
    assert effects==[('A','A-data'),('A','transfer')],'transfer-tail calls produce no local tool effects'
    result=run_batch(report.active,(ToolCall('next','same'),),catalog)
    assert result.receipts==(CallResult('next','B','same','B-data'),),'the next model batch uses the newly active routine namespace'
    ordinary=run_batch(a,(ToolCall('description','description'),ToolCall('after-data','same')),catalog)
    assert ordinary.active is a and ordinary.receipts[0].value=={'name':'B','instructions':'ordinary data','functions':[]},'Agent-shaped structured data stays ordinary tool data'
    assert isinstance(interpret_raw_tool_return(b),AgentReturn)and isinstance(interpret_raw_tool_return({'name':'B'}),DataReturn),'only actual Agent objects denote a control transfer'
    failed=run_batch(a,(ToolCall('failed','fail'),ToolCall('after-failure','same')),catalog)
    assert failed.active is a and failed.receipts==(CallFailed('failed','A','fail','declared-local-failure'),CallResult('after-failure','A','same','A-data')),'a declared ordinary tool failure does not create a handoff or discard later work'
    assert run_batch(a,(),catalog).receipts==()and run_batch(a,(),catalog).active is a,'an empty batch preserves its active routine'
    fallback=run_batch(a,(ToolCall('removed','removed'),ToolCall('tail-after-removed','same')),catalog)
    assert fallback.active is a and fallback.receipts==(Transfer('removed','A','removed','A'),CallSkipped('tail-after-removed','A','same')),'the supplied safe-target policy handles a removed routine without executing the batch tail'

    class Specialist(Agent):
        pass
    specialized=Specialist('B','specialized refund')
    source_agent=Agent('source','front desk',(Tool('forward',lambda:specialized),))
    specialized_catalog=RoutineCatalog((source_agent,b))
    specialized_report=run_batch(source_agent,(ToolCall('specialized','forward'),),specialized_catalog)
    assert specialized_report.active is b and specialized_report.receipts==(Transfer('specialized','source','forward','B'),),'Agent subclasses retain control-return semantics'
    events=[]
    destination=Agent('destination','local specialist')
    def first_tool():
        events.append(('invoke','first'));return 'first-data'
    def move_tool():
        events.append(('invoke','move'));return destination
    def tail_tool():
        events.append(('invoke','tail'));return 'unrequested'
    original=Agent('original','local front desk',(Tool('first',first_tool),Tool('move',move_tool),Tool('tail',tail_tool)))
    class TracedCatalog(RoutineCatalog):
        def function(self,owner,name):
            events.append(('lookup',name));return super().function(owner,name)
    traced_catalog=TracedCatalog((original,destination))
    run_batch(original,(ToolCall('one','first'),ToolCall('two','move'),ToolCall('three','tail')),traced_catalog)
    assert events==[('lookup','first'),('lookup','move'),('lookup','tail'),('invoke','first'),('invoke','move')],'all original-owner lookups precede every invocation'

@pytest.mark.skip('Part 4')
def test_typed_routine_receipt_ndjson():
    """Project each typed local receipt into complete public NDJSON using the supplied async driver."""
    catalog,_=tools_fixture();report=run_batch(catalog.agent('A'),(ToolCall('move','handoff'),ToolCall('not-called','same')),catalog)
    receipts=(CallResult('data','A','same',{'name':'B','items':[1,None,'行\n二']}),*report.receipts,CallFailed('bad','B','same','x\ny'),Reply('B','done\n退'))
    class Source:
        def __init__(self,items):self.items=iter(items);self.closed=False;self.pulls=0
        def __aiter__(self):return self
        async def __anext__(self):
            self.pulls+=1
            try:return next(self.items)
            except StopIteration:raise StopAsyncIteration
        async def aclose(self):self.closed=True
    async def collect():
        source=Source(receipts);rows=[line async for line in publish_receipts(source,ReceiptProjection())]
        return source,rows
    source,lines=asyncio.run(collect());rows=[json.loads(line)for line in lines]
    assert rows==[{'kind':'call-result','call_id':'data','tool':'same','owner':'A','result':{'name':'B','items':[1,None,'行\n二']}},{'kind':'transfer','call_id':'move','tool':'handoff','sender':'A','target':'B'},{'kind':'call-skipped','call_id':'not-called','tool':'same','owner':'A','reason':'after-transfer'},{'kind':'call-failed','call_id':'bad','tool':'same','owner':'B','error':'x\ny'},{'kind':'reply','sender':'B','content':'done\n退'}],'each typed receipt keeps its own complete domain fields and data values'
    assert 'result'not in rows[2]and rows[2]['kind']=='call-skipped','a skipped tool call has no fabricated execution result'
    assert all(line.endswith(b'\n')and line.count(b'\n')==1 for line in lines)and source.closed,'the supplied writer and driver deliver complete NDJSON records and close the source'
    async def stop():
        source=Source(receipts);stream=publish_receipts(source,ReceiptProjection());first=await anext(stream);pulls=source.pulls;await stream.aclose();return source,first,pulls
    stopped,first,pulls=asyncio.run(stop())
    assert pulls==1 and stopped.closed and json.loads(first)['call_id']=='data','the supplied driver closes without pulling an unrequested receipt'

@pytest.mark.skip('Part 5')
def test_nested_independent_caller_runs(tmp_path):
    """Compose own sequential batch continuation and independent nested caller-run activation."""
    from routinehop.models import BatchStep,ChildRun,RunNode,OwnBatchAudit,ChildAudit
    from routinehop.run_support import RunCatalog,RunDesk
    base,_=tools_fixture();catalog=RunCatalog(tuple(base.agent(n)for n in base.names()))
    first=RunNode('child-one','A',(BatchStep('child-before',(ToolCall('c1-data','same'),)),BatchStep('child-move',(ToolCall('c1-move','handoff'),))))
    second=RunNode('child-two','A',(BatchStep('child-only',(ToolCall('c2-data','same'),)),))
    root=RunNode('caller-root','A',(BatchStep('move',(ToolCall('r-move','handoff'),)),ChildRun('independent-one',first),BatchStep('continue',(ToolCall('r-data','same'),)),ChildRun('independent-two',second)))
    audit=RunDesk().audit(root,catalog)
    assert audit.steps[0]==OwnBatchAudit('move','A','B',(Transfer('r-move','A','handoff','B'),))and audit.steps[2]==OwnBatchAudit('continue','B','B',(CallResult('r-data','B','same','B-data'),)),'a caller run continues from its own preceding batch active routine'
    assert audit.final=='B'and audit.steps[-1].run.final=='A','a child run cannot change its caller active routine even as the final step'
    assert audit.steps[1].run.initial=='A'and audit.steps[1].run.history[0]==CallResult('c1-data','A','same','A-data')and audit.steps[3].run.history==(CallResult('c2-data','A','same','A-data'),),'each child run starts from its own declared routine independently of parent and siblings'
    assert audit.history==(Transfer('r-move','A','handoff','B'),CallResult('r-data','B','same','B-data')),'caller history contains only its own executed batches in declared order'
    assert tuple(step.step_id for step in audit.steps)==('move','independent-one','continue','independent-two')and isinstance(audit.steps[1],ChildAudit),'nested run evidence retains the original interleaving of own batches and children'
    empty=RunNode('empty-parent','A',(ChildRun('only-child',RunNode('empty-child','B')),))
    empty_audit=RunDesk().audit(empty,catalog)
    assert empty_audit.final=='A'and empty_audit.history==()and empty_audit.steps[0].run.final=='B','a caller without own batches retains its declared active routine and own empty history'
    continuation=Continuation(audit.run_id,catalog.agent(audit.final),audit.history,(41,42));store=RoutineStore(tmp_path);store.save(continuation)
    fresh,_=tools_fixture();reopened=RoutineStore(tmp_path).load(audit.run_id,fresh)
    assert reopened==Continuation(audit.run_id,fresh.agent('B'),audit.history,(41,42))and reopened.active is fresh.agent('B'),'nested caller audit can persist and reopen its actual own continuation'
    counted_base,invocations=tools_fixture()
    counted_catalog=RunCatalog(tuple(counted_base.agent(n)for n in counted_base.names()))
    counted_audit=RunDesk().audit(root,counted_catalog)
    assert counted_audit==audit and invocations==[('A','transfer'),('A','A-data'),('A','transfer'),('B','B-data'),('A','A-data')],'caller composition executes each declared own batch exactly once'
