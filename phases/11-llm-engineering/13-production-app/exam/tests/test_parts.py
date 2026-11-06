import asyncio,json,time
import sqlite3
from dataclasses import replace
from decimal import Decimal
import pytest
from rolloutlab.contracts import PromptTemplate as Prompt,Request,Safety,Immediate,PreparedMiss,RequestObservation as Seen,PaidObservation as Paid,AttemptFact as Fact,ProviderReply,ProviderFailure,Experiment,Assignment,Snapshot,BranchDelivery
from rolloutlab import routing
from rolloutlab.routing import get_prompt_record,stable_bucket
from rolloutlab.ledger import Ledger,replay_observations
from rolloutlab.prepare import prepare_safe_request
from rolloutlab.primitives import cache_key
from rolloutlab.store import RolloutStore
from rolloutlab.experiment import execute_experiment
from rolloutlab.wire_driver import publish_branch_completions
from rolloutlab.deployment import deployment_report
def registry():
    return {"chat":{"v1":Prompt("chat","v1","control {query} / {style}","fast",99),"v2":Prompt("chat","v2","variant {query} / {style}","careful",199)},"code":{"v9":Prompt("code","v9","code {query}","code-model",71)}}
def request(name="r",user="user"):
    return Request(name,user,"chat","v1","question",{"style":"brief"})
def allow(text):return Safety(True,text)
def guard(text):return Safety(False,"Refused.") if "UNSAFE" in text else Safety(True,text)
def observed_fixture():
    rows=[]
    for i in range(400):
        identity="request-"+str(i);user="user-"+str(i%3);status=("approved","blocked_output","error","blocked_input")[i%4]
        rows.append(Seen(identity,user,"chat","v1",status,i%4==0))
        if i%4 in (1,2):rows.append(Paid(identity,user,"experiment","served","v1",0,"fast",11,7,"0.0010"))
        if i%5==0:rows.append(Paid(identity,user,"experiment","shadow","v2",0,"careful",13,17,"0.00200"))
    return tuple(rows)
def fixture_summary(rows):
    # Independent fixture arithmetic; no application fold is used for the expected result.
    paid=[row for row in rows if isinstance(row,Paid)]
    return {"requests":400,"cache_hits":100,"status_counts":{"approved":100,"blocked_output":100,"error":100,"blocked_input":100},"paid_attempts":280,"input_tokens":3240,"output_tokens":2760,"cost":Decimal("0.360"),"cost_by_user":{name:sum((Decimal(row.cost_text) for row in paid if row.user==name),Decimal(0)) for name in ("user-0","user-1","user-2")},"cost_by_model":{"fast":Decimal("0.200"),"careful":Decimal("0.160")},"cost_by_role":{"served":Decimal("0.200"),"shadow":Decimal("0.160")}}
@pytest.mark.skip("Part 1")
def test_prompt_preparation_and_observation_replay(monkeypatch):
    """Repair scoped records, stable cohorts, cache safety and responsive full-fact replay."""
    templates=registry();req=request();ledger=Ledger()
    result=prepare_safe_request(req,templates,{},allow,guard,ledger)
    assert isinstance(result,PreparedMiss) and result.prompt==templates["chat"]["v1"] and result.rendered=="control question / brief","prepared misses retain the selected prompt record and rendered variables"
    assert req.variables=={"style":"brief"} and result.request.variables=={"style":"brief","query":"question"} and ledger.records==[],"preparation keeps caller variables and leaves model-call accounting to execution"
    with monkeypatch.context() as patch:
        patch.setattr(routing,"hash",lambda value:0,raising=False)
        assert [stable_bucket(user,experiment) for user,experiment in (("user","exp"),("alice","rollout"),("bob","rollout"),("你好","shadow"),("","x"))]==[88, 62, 45, 71, 57],"user cohorts remain the declared stable assignments across process environments"
    for missing in (("chat","v9"),("missing","v1")):
        with pytest.raises(KeyError):get_prompt_record(templates,*missing)
    calls=[]
    def input_check(text):calls.append(("input",text));return Safety(text!="blocked","No input." if text=="blocked" else text)
    def output_check(text):calls.append(("output",text));return guard(text)
    cache={cache_key(req,req.query):"UNSAFE cached original"};ledger=Ledger()
    cached=prepare_safe_request(req,templates,cache,input_check,output_check,ledger)
    assert cached==Immediate("r","Refused.","blocked_output",True) and calls==[("input","question"),("output","UNSAFE cached original")],"cached outputs receive both safety stages before delivery"
    assert ledger.records==[Seen("r","user","chat","v1","blocked_output",True)] and ledger.summary()["paid_attempts"]==0,"cached delivery keeps request provenance without invented paid attempts"
    calls.clear();blocked=replace(req,query="blocked");cache[cache_key(blocked,"blocked")]="old answer"
    result=prepare_safe_request(blocked,templates,cache,input_check,output_check,Ledger())
    assert result.status=="blocked_input" and result.text=="No input." and calls==[("input","blocked")],"blocked input never reaches cached content or the output stage"
    empty=prepare_safe_request(req,templates,{cache_key(req,req.query):""},allow,guard,Ledger())
    assert empty.text=="" and empty.cache_hit,"a safe empty cached answer remains an observed cache hit"
    rows=observed_fixture();expected=fixture_summary(rows);started=time.perf_counter()
    summary,retained=replay_observations(Ledger(),iter(rows))
    assert summary==expected and retained==rows,"observation replay retains every request and paid fact with complete paid-versus-served totals"
    elapsed=time.perf_counter()-started
    assert elapsed<0.04,"large observation replays should stay responsive"
    ledger=Ledger();ledger.append(rows[0]);outside=ledger.summary();outside["status_counts"].clear()
    assert ledger.summary()["status_counts"]=={"approved":1},"returned summary objects cannot rewrite retained observability state"
@pytest.mark.skip("Part 2")
def test_rollout_snapshot(tmp_path):
    """Persist prompt versions, user-experiment buckets and every typed observed usage fact."""
    templates=registry();prompts=tuple(p for family in templates.values() for p in family.values())
    assignments=(Assignment("same-user","exp-A",17),Assignment("same-user","exp-B",91),Assignment("other","exp-A",99))
    observations=(Seen("same-request","same-user","chat","v1","blocked_output",False),Paid("same-request","same-user","exp-A","served","v1",0,"fast",101,203,"0.0010000000000000000001"),Paid("same-request","same-user","exp-A","shadow","v2",0,"careful",303,407,"0.0200"),Seen("cache","other","chat","v1","approved",True))
    original=Snapshot(prompts,assignments,observations);path=tmp_path/"rollouts.sqlite";store=RolloutStore(path)
    store.save_snapshot(original);store.close();store=RolloutStore(path);loaded=store.load_snapshot()
    assert loaded.prompts==prompts,"reopened snapshots retain each named prompt version and its actual model configuration"
    assert loaded.assignments==assignments,"one user retains independent stable bucket assignments for every experiment"
    assert loaded.observations==observations,"observed paid roles and original token counts survive independently of served text"
    assert loaded.observations[1].cost_text=="0.0010000000000000000001" and loaded.observations[2].cost_text=="0.0200","paid cost spellings remain exact original evidence"
    updated=Snapshot((replace(prompts[0],template="changed {query}\n你好",max_output_tokens=111),),assignments,observations+(Paid("same-request","same-user","exp-A","served","v1",1,"fallback",17,19,"0.0001"),))
    store.save_snapshot(updated);store.close();store=RolloutStore(path)
    assert store.load_snapshot()==updated,"a new complete snapshot replaces prompt configuration while retaining every supplied attempt"
    assert assignments[0].bucket<20 and not assignments[0].bucket<10 and store.load_snapshot().assignments==assignments,"traffic percentage changes selection while persistent assignments remain stable buckets"
    store.save_snapshot(Snapshot((),(),()));assert store.load_snapshot()==Snapshot((),(),()),"an empty complete snapshot removes all prior state"
    store.close()
    atomic_path=tmp_path/"atomic.sqlite";atomic=RolloutStore(atomic_path)
    atomic.save_snapshot(original);atomic.close()
    connection=sqlite3.connect(atomic_path)
    connection.execute("CREATE TRIGGER reject_observation BEFORE INSERT ON observations WHEN instr(NEW.record,'reject-request')>0 BEGIN SELECT RAISE(ABORT,'blocked fixture observation'); END")
    connection.commit();connection.close();atomic=RolloutStore(atomic_path)
    rejected=Snapshot((replace(prompts[0],template="new {query}"),),assignments,(Seen("reject-request","same-user","chat","v1","approved",False),))
    with pytest.raises(sqlite3.IntegrityError,match="blocked fixture observation"):
        atomic.save_snapshot(rejected)
    atomic.close();atomic=RolloutStore(atomic_path)
    assert atomic.load_snapshot()==original,"failed snapshot replacement retains the previous complete snapshot after reopen"
    atomic.close()
@pytest.mark.skip("Part 3")
def test_rollout_shadow_execution():
    """Execute distinct served/shadow roles and account only actually observed paid attempts."""
    templates=registry();base=PreparedMiss(replace(request(),variables={"query":"question","style":"brief"}),templates["chat"]["v1"],"unused")
    fact1=Fact("fast",11,101,"0.0010");fact2=Fact("careful",17,203,"0.0020000000000000000001")
    async def scenario(mode,pct,replies):
        calls=[];ledger=Ledger()
        async def provider(record,text):
            calls.append((record.version,record.model,text));value=replies[record.version]
            if isinstance(value,Exception):raise value
            return value
        outcome=await execute_experiment(base,Experiment("exp","chat","v1","v2",pct,mode),templates,provider,guard,lambda record,text,status:99 if record.version=="v2" else 1,ledger)
        return outcome,calls,ledger
    async def run():
        replies={"v1":ProviderReply("control answer",(fact1,)),"v2":ProviderReply("better shadow answer",(fact2,))}
        result,calls,ledger=await scenario("rollout",0,replies)
        assert result.served.version=="v1" and result.shadow==() and [x[0] for x in calls]==["v1"],"zero-percent rollout executes only the served control branch"
        result,calls,ledger=await scenario("rollout",100,replies)
        assert result.served.version=="v2" and result.shadow==() and [x[0] for x in calls]==["v2"] and ledger.records[-1].version=="v2","full rollout executes only the served variant branch"
        result,calls,ledger=await scenario("shadow",0,replies)
        assert result.served.version=="v1" and result.served.served_text=="control answer" and len(result.shadow)==1 and result.shadow[0].version=="v2" and [x[0] for x in calls]==["v1","v2"],"shadow mode observes every eligible miss while the control remains served"
        assert [x[2] for x in calls]==["control question / brief","variant question / brief"],"each branch renders its own scoped prompt version with prepared variables"
        assert result.shadow[0].quality==99 and result.served.quality==1 and ledger.summary()["requests"]==1 and ledger.summary()["paid_attempts"]==2,"shadow quality does not promote a branch or duplicate the served request"
        unsafe={"v1":ProviderReply("UNSAFE raw output with many observed tokens",(fact1,replace(fact1,model="fallback",output_tokens=307))),"v2":ProviderReply("UNSAFE shadow raw",(fact2,))}
        result,calls,ledger=await scenario("shadow",23,unsafe)
        paid=[x for x in ledger.records if isinstance(x,Paid)]
        assert result.served.status=="blocked_output" and result.served.served_text=="Refused." and result.shadow[0].served_text=="Refused.","output safety may replace branch text without changing execution roles"
        assert [(x.role,x.version,x.ordinal,x.model,x.input_tokens,x.output_tokens,x.cost_text) for x in paid]==[("served","v1",0,"fast",11,101,"0.0010"),("served","v1",1,"fallback",11,307,"0.0010"),("shadow","v2",0,"careful",17,203,"0.0020000000000000000001")],"safety-replaced outputs retain all original observed paid attempts and role provenance"
        result,calls,ledger=await scenario("shadow",100,{"v1":replies["v1"],"v2":ProviderFailure("shadow down",(fact2,))})
        assert result.served.status=="approved" and result.served.served_text=="control answer" and result.shadow[0].status=="error" and ledger.summary()["paid_attempts"]==2,"an observed shadow failure cannot erase served success or its paid evidence"
        result,calls,ledger=await scenario("shadow",100,{"v1":ProviderFailure("control down"),"v2":replies["v2"]})
        assert result.served.status=="error" and result.served.served_text=="Service unavailable." and result.shadow[0].status=="approved","a failed served branch cannot publish successful shadow text"
        assert ledger.summary()["paid_attempts"]==1 and ledger.summary()["cost_by_role"]=={"shadow":Decimal(fact2.cost_text)} and ledger.summary()["status_counts"]=={"error":1},"unobserved failure invents no usage and the request keeps the served outcome"
        result,calls,ledger=await scenario("rollout",88,replies)
        assert result.bucket==88 and result.served.version=="v1" and [x[0] for x in calls]==["v1"],"the exact percentage boundary stays outside the variant cohort"
        successful_facts=(fact1,replace(fact1,model="fallback",input_tokens=23,output_tokens=29,cost_text="0.000500"))
        result,calls,ledger=await scenario("rollout",0,{"v1":ProviderReply("approved after observed attempts",successful_facts),"v2":replies["v2"]})
        paid=tuple(row for row in ledger.records if isinstance(row,Paid))
        assert result.served.status=="approved" and result.served.attempts==paid and [(row.ordinal,row.model,row.input_tokens,row.output_tokens,row.cost_text) for row in paid]==[(0,"fast",11,101,"0.0010"),(1,"fallback",23,29,"0.000500")] and ledger.summary()["paid_attempts"]==2 and ledger.summary()["requests"]==1,"approved delivery retains every original paid attempt in order"
    asyncio.run(run())
@pytest.mark.skip("Part 4")
def test_role_aware_sse():
    """Project served content and shadow-only telemetry through a supplied SSE driver."""
    usage={"attempts":2,"input_tokens":28,"output_tokens":408,"cost_text":"0.0010000000000000000001"}
    served=BranchDelivery("request-A","served","v1","blocked_output","Refused.",None,usage)
    shadow=BranchDelivery("request-B","shadow","v2","approved","PRIVATE shadow text",99,{"attempts":1,"input_tokens":17,"output_tokens":203,"cost_text":"0.0200"})
    failed=BranchDelivery("request-C","served","v1","error","Service unavailable.",None,{"attempts":0,"input_tokens":0,"output_tokens":0,"cost_text":"0"})
    pulled=[];closed=[]
    async def source():
        try:
            for item in (served,shadow,failed):pulled.append(item.request_id);yield item
        finally:closed.append(True)
    def parse(frame):
        lines=frame.splitlines();assert len(lines)==3 and frame.endswith("\n\n"),"the supplied driver preserves complete SSE event framing"
        return lines[0][7:],json.loads(lines[1][6:])
    async def run():
        stream=publish_branch_completions(source());event,first=parse(await stream.__anext__())
        assert event=="content" and first=={"request_id":"request-A","role":"served","version":"v1","text":"Refused."} and pulled==["request-A"],"served branches publish the safety-approved delivery text under their supplied current identity"
        event,telemetry=parse(await stream.__anext__())
        assert event=="served" and telemetry["paid_usage"]==usage and telemetry["status"]=="blocked_output" and telemetry["quality"] is None,"served telemetry retains original observed billing even for a short refusal"
        event,telemetry=parse(await stream.__anext__())
        assert event=="shadow" and telemetry=={"request_id":"request-B","role":"shadow","version":"v2","status":"approved","quality":99,"paid_usage":shadow.paid_usage} and "PRIVATE" not in json.dumps(telemetry),"shadow completions publish only status quality and observed usage telemetry"
        rest=[parse(frame) async for frame in stream]
        assert [event for event,data in rest]==["content","served"] and rest[-1][1]["paid_usage"]==failed.paid_usage,"unobserved errors keep an explicit zero-usage branch observation"
        assert closed==[True] and pulled==["request-A","request-B","request-C"],"normal completion closes the supplied completed-branch source"
        pulled.clear();closed.clear();early=publish_branch_completions(source());await early.__anext__();await early.aclose()
        assert pulled==["request-A"] and closed==[True],"early close stops the supplied driver before a later branch is requested"
        approved=BranchDelivery("request-D","served","v2","approved","",0,usage)
        async def approved_source():yield approved
        approved_events=[parse(frame) async for frame in publish_branch_completions(approved_source())]
        assert approved_events==[("content",{"request_id":"request-D","role":"served","version":"v2","text":""}),("served",{"request_id":"request-D","role":"served","version":"v2","status":"approved","quality":0,"paid_usage":usage})],"approved served completions retain empty content and zero quality as observed"
    asyncio.run(run())
    assert served.paid_usage==usage and shadow.served_text=="PRIVATE shadow text","event projection preserves original completed-branch evidence"
@pytest.mark.skip("Part 5")
def test_deployment_registry_evidence():
    """Report actual nested prompt records and template-scoped experiment references."""
    templates=registry();experiments={"good":Experiment("good","chat","v1","v2",40),"wrong-family":Experiment("wrong-family","chat","v1","v9",10),"orphan":Experiment("orphan","missing","v1","v2",0)}
    templates["chat"]["broken"]=Prompt("other","wrong","text","unknown",10)
    templates["code"]["bad"]=Prompt("code","bad","text","also-unknown",10)
    before={name:dict(versions) for name,versions in templates.items()};models={"fast","careful","code-model"}
    report=deployment_report(templates,experiments,models,"fast")
    assert not report["configuration_ready"] and report["templates"]["chat"]["versions"]["v1"]["valid"] and report["templates"]["chat"]["experiments"]["good"]["valid"],"static readiness reports valid records and experiments alongside broken siblings"
    bad=report["templates"]["chat"]["versions"]["broken"]
    assert [(x["path"],x["code"]) for x in bad["issues"]]==[(("templates","chat","broken","name"),"record_name"),(("templates","chat","broken","version"),"record_version"),(("templates","chat","broken","model"),"unknown_model")],"record evidence retains outer identity mismatches and its actual model path"
    assert report["templates"]["code"]["versions"]["bad"]["issues"]==[{"path":("templates","code","bad","model"),"code":"unknown_model"}],"every deployed sibling uses its actual model rather than the global primary context"
    wrong=report["templates"]["chat"]["experiments"]["wrong-family"]
    assert not wrong["valid"] and wrong["control_path"]==("templates","chat","v1") and wrong["variant_path"] is None and wrong["issues"]==[{"path":("experiments","wrong-family","variant"),"code":"missing_variant"}],"experiment versions resolve only within their declared template family"
    assert report["unresolved_experiments"]["orphan"]["issues"]==[{"path":("experiments","orphan","template"),"code":"missing_template"}] and len(report["issues"])==6,"missing-template experiments and all sibling issues remain explicit evidence"
    assert templates==before and bad["record"] is templates["chat"]["broken"],"configuration reporting keeps the original records and nested input unchanged"
    clean=deployment_report(registry(),{"good":experiments["good"]},models,"missing-primary-context")
    assert clean["configuration_ready"] and clean["issues"]==[] and clean["templates"]["chat"]["experiments"]["good"]["variant_path"]==("templates","chat","v2"),"static readiness uses deployed record models and exact scoped version references"
    assert deployment_report({}, {},models,"fast")=={"configuration_ready":True,"templates":{},"unresolved_experiments":{},"issues":[]},"an empty configuration report contains explicit empty evidence containers"
    empty_family=deployment_report({"empty":{}},{"empty-exp":Experiment("empty-exp","empty","v1","v2",0)},models,"fast")
    missing_refs=[{"path":("experiments","empty-exp","control"),"code":"missing_control"},{"path":("experiments","empty-exp","variant"),"code":"missing_variant"}]
    assert empty_family=={"configuration_ready":False,"templates":{"empty":{"versions":{},"experiments":{"empty-exp":{"valid":False,"control_path":None,"variant_path":None,"issues":missing_refs}}}},"unresolved_experiments":{},"issues":missing_refs},"declared empty template families retain scoped missing-reference evidence"
    invalid_record=registry();invalid_record["chat"]["v2"]=replace(invalid_record["chat"]["v2"],model="unknown")
    existing=deployment_report(invalid_record,{"good":experiments["good"]},models,"fast")
    assert not existing["configuration_ready"] and not existing["templates"]["chat"]["versions"]["v2"]["valid"] and existing["templates"]["chat"]["experiments"]["good"]=={"valid":True,"control_path":("templates","chat","v1"),"variant_path":("templates","chat","v2"),"issues":[]},"existing references remain valid independently of their record issues"
