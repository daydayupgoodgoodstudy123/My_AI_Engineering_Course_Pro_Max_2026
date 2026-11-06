import asyncio,json,re,sqlite3,time
from dataclasses import replace
from decimal import Decimal,localcontext
from threading import Barrier,Thread
import pytest
from quotaflow.contracts import BucketState,Usage,Price,US
from quotaflow.memory import MemoryStore
from quotaflow.legacy import LegacyService
from quotaflow.bucket import tier_policy,refill_exact,commit_admission
from quotaflow.store import LedgerStore
from quotaflow.admission import AdmissionController
from quotaflow.metrics import export_batches
from quotaflow.report import usage_report
POLICIES={"free":{"capacity":50,"refill_rate":3,"max_requests_per_min":2}}
def record(key="a",user="u",model="m",admitted=True,inputs=7,cached=3,outputs=2,cost="0.0000039"):
    return Usage(key,user,model,admitted,inputs,cached,outputs,cost)
def metrics(text):
    """Parse this exercise's finite Prometheus HELP/TYPE/label/sample subset."""
    assert text.endswith("\n"),"an exposition ends with a complete sample line"
    result={};types={}
    for line in text.split("\n")[:-1]:
        if line.startswith("# TYPE "):
            _,_,name,kind=line.split();types[name]=kind;continue
        if line.startswith("# HELP "):continue
        match=re.fullmatch(r'([a-z_]+)\{(.*)\} ([^ ]+)',line)
        assert match,"every exposition line is a complete metric sample"
        name,labels,value=match.groups();items=[];position=0
        while position<len(labels):
            found=re.match(r'([a-z_]+)=("(?:[^"\\]|\\.)*")(?:,|$)',labels[position:])
            assert found,"metric labels retain quoted values"
            items.append((found[1],json.loads(found[2],strict=False)));position+=found.end()
        key=(name,tuple(sorted(items)))
        assert key not in result,"each metric label set appears once per snapshot"
        result[key]=Decimal(value)
    assert types=={name:"counter" for name in ("quota_requests_total","quota_model_calls_total","quota_tokens_total","quota_cost_dollars_total")},"all emitted counters have declared types"
    return result
def sample(parsed,name,user,model,**extra):
    return parsed[(name,tuple(sorted({"user":user,"model":model,**extra}.items())))]
@pytest.mark.skip("Part 1")
def test_legacy_quota():
    """Repair source-style tier lookup, fractional refill and admission bookkeeping."""
    store=MemoryStore();store.save("u",BucketState(10,0))
    service=LegacyService(store,POLICIES)
    assert service.admit("u",1,0).tokens_remaining==9,"the selected tier supplies the expected token policy"
    assert tier_policy("missing",POLICIES) is POLICIES["free"],"an unknown tier uses the free policy"
    state=BucketState(0,0)
    for now in (100_000,200_000,400_000):state=refill_exact(state,POLICIES["free"],now)
    assert (state.tokens,state.remainder,state.last_refill_us)==(1,200_000,400_000),"short refill intervals retain their combined credit"
    denied=BucketState(2,400_000,700_000,(100_000,),7)
    assert commit_admission(denied,9,False,400_000)==denied,"a rejected request leaves admission usage unchanged"
    approved=commit_admission(denied,2,True,400_000)
    assert approved==BucketState(0,400_000,700_000,(100_000,400_000),9),"an allowed request records exactly its consumption"
    saturated=refill_exact(BucketState(49,0,900_000),POLICIES["free"],500_000)
    assert saturated==BucketState(50,500_000,0),"capacity discards credit beyond a full bucket"
    assert refill_exact(state,POLICIES["free"],99)==state,"backward time cannot increase credit or rewind the effective clock"
    assert refill_exact(BucketState(50,0,900_000),POLICIES["free"],0).remainder==0,"full buckets retain no fractional excess"
    with pytest.raises(ValueError):service.admit("u",True,0)
    stress={"free":{"capacity":10_000,"refill_rate":317,"max_requests_per_min":10}}
    large=MemoryStore();large.save("idle",BucketState(7,0,123_456))
    started=time.perf_counter()
    result=LegacyService(large,stress).admit("idle",13,8_000_123)
    elapsed=time.perf_counter()-started
    assert result.allowed and result.tokens_remaining==2530,"long-idle admission retains the complete refill and debit result"
    assert large.load("idle")==BucketState(2530,8_000_123,162_447,(8_000_123,),13),"long-idle admission retains exact state and request evidence"
    assert elapsed<0.08,"long-idle quota requests should stay responsive"
@pytest.mark.skip("Part 2")
def test_ledger_roundtrip(tmp_path):
    """Persist the spent bucket and exact cost ledger together across reopen."""
    path=tmp_path/"quota.sqlite";store=LedgerStore(path)
    stamp=2**53+17
    state=BucketState(17,stamp,999_983,(stamp-2,stamp-1,stamp),2**53+23)
    first=record(cost="0.00000000000000000012345678901234567890")
    second=record("b",model="模型\u2028名称",admitted=False,cost="000.0012300")
    store.save_and_log("u",state,first);store.save_and_log("u",state,second);store.close()
    store=LedgerStore(path)
    assert store.load("u")==state,"a reopened quota ledger retains the entire spent bucket exactly"
    assert store.ledger()==[first,second],"ledger records retain order, identity and original decimal spelling"
    assert store.load("absent") is None,"missing users do not acquire a persisted bucket"
    changed=replace(state,tokens=1,remainder=42,total_used=state.total_used+16)
    with pytest.raises(sqlite3.IntegrityError):store.save_and_log("u",changed,first)
    store.close();store=LedgerStore(path)
    assert store.load("u")==state and store.ledger()==[first,second],"a failed ledger append preserves the associated prior bucket"
    third=record("c",cost="-0.0000");store.save_and_log("u",changed,third);store.close();store=LedgerStore(path)
    assert store.load("u")==changed and store.ledger()[-1]==third,"later successful admission state and exact zero cost survive reopen"
    store.close()
    store=LedgerStore(path)
    coincident=replace(changed,rpm=(stamp-2,stamp-2,stamp))
    store.save_and_log("u",coincident,record("coincident"));store.close();store=LedgerStore(path)
    assert store.load("u")==coincident,"persisted RPM history retains coincident admitted requests"
    later=replace(coincident,last_refill_us=stamp+101)
    store.save_and_log("u",later,record("later-clock"));store.close();store=LedgerStore(path)
    assert store.load("u")==later,"later quota snapshots retain the supplied refill clock"
    store.close()
@pytest.mark.skip("Part 3")
def test_atomic_admission():
    """Joint retry uses one exact snapshot and one atomic per-user decision."""
    policies={"free":{"capacity":10,"refill_rate":3,"max_requests_per_min":2}}
    store=MemoryStore();control=AdmissionController(store,policies)
    initial=BucketState(0,59_000_000,500_000,(1_000_000,2_000_000),10);store.save("u",initial)
    blocked=control.admit("u",10,59_000_000)
    assert (blocked.allowed,blocked.reason,blocked.retry_after_us)==(False,"both",3_166_667),"retry satisfies both limits at the earliest whole microsecond"
    assert store.load("u")==initial,"a denied admission does not spend tokens or add request evidence"
    before=control.admit("u",10,62_166_666)
    assert not before.allowed and before.retry_after_us==1,"the microsecond before eligibility remains denied"
    granted=control.admit("u",10,62_166_667)
    assert granted.allowed and granted.retry_after_us==0 and granted.tokens_remaining==0,"the exact eligibility boundary admits the complete demand"
    assert store.load("u").rpm==(62_166_667,) and store.load("u").total_used==20,"expired admitted requests leave the sliding window"
    impossible=control.admit("u",11,62_166_667)
    assert (impossible.allowed,impossible.reason,impossible.retry_after_us)==(False,"capacity",None),"demand above capacity has no finite retry"
    history=BucketState(10,59_000_000,0,(1_000_000,2_000_000,3_000_000,4_000_000))
    store.save("history",history)
    assert control.admit("history",1,59_000_000).retry_after_us==4_000_000,"retry waits until a slot exists in the entire admitted history"
    store.save("backward",BucketState(10,100_000_000,0,(99_000_000,),0))
    assert control.admit("backward",1,98_000_000).allowed and store.load("backward").rpm==(99_000_000,100_000_000),"backward clock admission uses the existing effective timestamp"
    class RacingStore(MemoryStore):
        def __init__(self):super().__init__();self.barrier=Barrier(2);self.access=[]
        def load(self,user):
            state=super().load(user);held=self.held(user);self.access.append(("load",held))
            if not held:self.barrier.wait(timeout=1)
            return state
        def save(self,user,state):self.access.append(("save",self.held(user)));super().save(user,state)
    race=RacingStore();race.states["last"]=BucketState(1,0)
    narrow={"free":{"capacity":1,"refill_rate":1,"max_requests_per_min":10}}
    controller=AdmissionController(race,narrow);answers=[];errors=[]
    def call():
        try:answers.append(controller.admit("last",1,0))
        except BaseException as exc:errors.append(exc)
    threads=[Thread(target=call) for _ in range(2)]
    for thread in threads:thread.start()
    for thread in threads:thread.join(timeout=2)
    assert not errors and len(answers)==2 and sum(x.allowed for x in answers)==1,"concurrent requests cannot both consume the final token"
    assert all(held for operation,held in race.access),"the complete state decision shares its user critical section"
    assert race.states["last"].tokens==0 and race.states["last"].total_used==1,"concurrent admission preserves one debit and one usage increment"
@pytest.mark.skip("Part 4")
def test_prometheus_batches():
    """Expose cumulative completed-batch counters with exact labels and billing scope."""
    user='team\\"north\nline\u2028tail';model='m\\"1'
    first=record(user=user,model=model,cost="0.00000000000000000012345678901234567890")
    denied=record("d",user,model,False,999,900,888,"99.99")
    other=record("z","other","x",True,1,1,0,"0.0000001")
    async def run():
        pulled=[]
        async def source():
            for batch in ((),(first,),(),(denied,other)):
                pulled.append(len(pulled));yield batch
        iterator=export_batches(source()).__aiter__()
        zero=await iterator.__anext__()
        assert len(pulled)==1 and metrics(zero)=={},"an empty completed batch publishes its own snapshot immediately"
        one=metrics(await iterator.__anext__())
        assert len(pulled)==2,"a completed usage batch is published before another is consumed"
        assert sample(one,"quota_tokens_total",user,model,kind="uncached_input")==4 and sample(one,"quota_tokens_total",user,model,kind="cached_input")==3,"input counter categories retain their disjoint billed usage"
        assert sample(one,"quota_cost_dollars_total",user,model)==Decimal(first.cost_text),"cost exposition preserves exact ledger decimals"
        same=metrics(await iterator.__anext__())
        assert same==one and len(pulled)==3,"an empty later batch preserves cumulative counters"
        final=metrics(await iterator.__anext__())
        assert sample(final,"quota_requests_total",user,model,outcome="allowed")==1 and sample(final,"quota_requests_total",user,model,outcome="denied")==1,"every admission decision contributes its own outcome counter"
        assert sample(final,"quota_model_calls_total",user,model)==1 and sample(final,"quota_tokens_total",user,model,kind="output")==2 and sample(final,"quota_cost_dollars_total",user,model)==Decimal(first.cost_text),"rejected proposed work adds no model call, billed tokens or cost"
        assert sample(final,"quota_model_calls_total","other","x")==1,"independent user-model counters retain their own values"
        with pytest.raises(StopAsyncIteration):await iterator.__anext__()
        async def denied_only_source():
            yield (record("only-denied","denied-only","cold",False,9,8,7,"12"),)
        denial_iterator=export_batches(denied_only_source()).__aiter__()
        denial_snapshot=metrics(await denial_iterator.__anext__())
        assert len(denial_snapshot)==7,"denied-only identities retain every metric series"
        assert sample(denial_snapshot,"quota_requests_total","denied-only","cold",outcome="denied")==1 and sample(denial_snapshot,"quota_requests_total","denied-only","cold",outcome="allowed")==0 and sample(denial_snapshot,"quota_model_calls_total","denied-only","cold")==0 and all(sample(denial_snapshot,"quota_tokens_total","denied-only","cold",kind=kind)==0 for kind in ("uncached_input","cached_input","output")) and sample(denial_snapshot,"quota_cost_dollars_total","denied-only","cold")==0,"denied-only identities have no completed usage or billed cost"
    asyncio.run(run())
@pytest.mark.skip("Part 5")
def test_usage_hierarchy():
    """Nested user/model/category evidence distinguishes billed cost and cache savings."""
    prices={"a":Price(Decimal("0.3"),Decimal("0.1"),Decimal("1.2")),"b":Price(Decimal("2"),Decimal("1"),Decimal("3"))}
    entries=[record("1","alice","a"),record("2","alice","a",True,1,1,0,"0.0000001"),record("3","bob","b",True,2,0,1,"0.000007"),record("4","alice","b",False,999,900,888,"99")]
    result=usage_report(iter(entries),prices);alice=result["users"]["alice"];model=alice["models"]["a"]
    assert list(result["users"])==["alice","bob"] and list(alice["models"])==["a","b"],"the report retains user and model appearance order"
    assert model["usage"]=={"uncached_input":{"tokens":4,"cost":Decimal("0.0000012")},"cached_input":{"tokens":4,"cost":Decimal("0.0000004")},"output":{"tokens":2,"cost":Decimal("0.0000024")}},"cached and uncached input occupy separate billed leaves"
    assert (model["billed"],model["cache_saved"],model["baseline"])==(Decimal("0.0000040"),Decimal("0.0000008"),Decimal("0.0000048")),"cache savings stay separate from the actual model bill"
    assert alice["totals"]["requests"]==3 and alice["models"]["b"]["denied"]==1 and alice["models"]["b"]["billed"]==0,"denied work retains evidence without a bill"
    assert result["totals"]["billed"]==Decimal("0.0000110") and result["totals"]["baseline"]==Decimal("0.0000118"),"account totals retain all exact model component costs"
    fine=Decimal("0.123456789012345678901234567890123456789")
    with localcontext() as context:
        context.prec=100;cost=fine/Decimal(1_000_000)
    tiny=usage_report([record("fine","u","fine",True,1,0,0,str(cost))],{"fine":Price(fine,Decimal(0),Decimal(0))})
    assert tiny["totals"]["billed"]==cost,"small component bills retain their complete decimal value"
    with pytest.raises(ValueError,match="unknown model"):usage_report([record("bad","u","absent")],prices)
    with pytest.raises(ValueError,match="disagrees"):usage_report([record("mismatch","u","a",cost="5")],prices)
    empty=usage_report([],prices)
    assert empty["users"]=={} and empty["totals"]["requests"]==0 and empty["totals"]["billed"]==0,"an empty usage ledger has explicit zero account totals"
    assert all(leaf["tokens"]==0 and leaf["cost"]==0 for leaf in alice["models"]["b"]["usage"].values()),"denied model usage remains zero in every token category"
    assert tuple(alice["totals"]["usage"][kind]["tokens"] for kind in ("uncached_input","cached_input","output"))==(4,4,2) and tuple(result["totals"]["usage"][kind]["tokens"] for kind in ("uncached_input","cached_input","output"))==(6,4,3),"user and account token totals include completed calls only"
