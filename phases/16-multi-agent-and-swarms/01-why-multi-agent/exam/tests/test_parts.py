import asyncio,csv,io,json,math
from dataclasses import replace
from time import perf_counter
import pytest
from splitcase.models import Fact,Role,Message,PrivateNote,Usage,CallRequest,CallSpec,Boundary,FixedDesign,Snapshot,CompletedStage,Scope,Leaf
from splitcase.service import ReplayService,prepare_design
from splitcase.usage import sum_branch_usage
from splitcase.store import SnapshotStore
from splitcase.accounting import role_peak_context,boundary_fact_losses,compare_fixed_design
from splitcase.stream import stream_comparisons
from splitcase.scopes import context_scope_report

def design_fixture():
    a=Role("coder","SYS",10);b=Role("reviewer","HELLO",4)
    calls=(CallSpec(11,"coder","abcdefghijklm",(),(),(),"code",6,2),CallSpec(12,"coder","x",(),(),(),"revision",0,1),CallSpec(13,"reviewer","1234567",(),(),(),"review",1,3))
    return FixedDesign("specialists",(a,b),calls)

def wide_request():
    width=32_000_000
    system="System contract: "+"s"*width
    user="Source documentation: "+"u"*width
    return CallRequest(2**70+9,"coder",system,user,"fixture output",17,3,(Fact("source","documentation"),))

@pytest.mark.skip("Part 1")
def test_addressed_replay_and_usage():
    """Repair specialist context boundaries and independent-call fixture usage."""
    role=Role("coder","Write code",100)
    messages=(Message("researcher","coder","limit is twenty",(Fact("limit","20/s"),),1,100),Message("coder","reviewer","candidate code",(Fact("code","draft"),),2,101))
    notes=(PrivateNote("reviewer","review-secret",(Fact("hidden","review only"),)),PrivateNote("coder","own scratch",(Fact("scratch","local"),)))
    shared=(Fact("task","rate limiter"),)
    view,value=ReplayService().preview(role,"Build limiter",shared,messages,notes,"limit")
    assert value=="20/s" and [fact.key for fact in view.facts]==["task","limit","scratch"] and "review-secret" not in view.user, "only intended role inputs belong to the specialist context"
    assert view.user=="Build limiter\n[From researcher]: limit is twenty\n[Private coder]: own scratch", "addressed summaries and owned notes retain their text and order"
    branches=(Usage(1,"researcher",7,5,2),Usage(2,"requirements",11,3,4),Usage(3,"researcher",0,0,1))
    assert sum_branch_usage(branches)=={"input_tokens":18,"output_tokens":8,"tool_calls":7,"total_tokens":26}, "fanout usage includes every independent branch and repeated role call"
    assert sum_branch_usage(())=={"input_tokens":0,"output_tokens":0,"tool_calls":0,"total_tokens":0}
    service=ReplayService()
    for system,user,expected in (("a","bcd",1),("汉𠀋","xy",1),("","",0),("ab","cdefg",1)):
        request=CallRequest(9,"coder",system,user,"reply",5,2)
        receipt=service.record(request)
        assert receipt.request is request and receipt.usage==Usage(9,"coder",expected,5,2), "each independent call retains its complete request and declared usage"
    request=wide_request()
    start=perf_counter();receipt=service.record(request)
    assert receipt.request is request and receipt.request.system is request.system and receipt.request.user is request.user and receipt.request.output=="fixture output" and receipt.usage==Usage(request.call_id,"coder",(64_000_000+len("System contract: ")+len("Source documentation: "))//4,17,3), "wide accounting retains both full context strings, fixture output and every usage field"
    elapsed=perf_counter()-start
    assert elapsed<0.0005, "a complete independent replay call remains responsive"
    assert messages[0].recipient=="coder" and notes[0].owner=="reviewer", "replay leaves caller records unchanged"

@pytest.mark.skip("Part 2")
def test_fixed_design_snapshot(tmp_path):
    """Reopen complete role/message/private/usage JSON values without narrowing."""
    huge=2**70+7
    message=Message("researcher","coder","facts\r\n世界",(Fact("limit","20/s"),),2**53+1,huge)
    note=PrivateNote("coder","private\n",(Fact("secret","only coder"),))
    call=CallSpec(huge,"coder","task\r\n",(Fact("task","do it"),),(message,),(note,),"output\n",2**54+1,0)
    design=FixedDesign("snapshot",(Role("reviewer","review",99),Role("coder","code",2**60+1)),(call,),(Boundary("summary","coder",("limit","optional"),("limit",),("limit",)),))
    snapshot=Snapshot("one\r\n任务",design,(Usage(huge,"coder",0,None,0),Usage(huge+1,"reviewer",2**54+3,0,1)),math.nextafter(0.1,math.inf))
    path=tmp_path/"design.json";store=SnapshotStore(path);store.save(snapshot)
    restored=SnapshotStore(path).load()
    assert restored==snapshot and restored.unit_cost.hex()==snapshot.unit_cost.hex(), "a complete fixed-design snapshot retains all exact values after reopening"
    assert type(restored.design.calls[0].call_id) is int and restored.design.calls[0].call_id==huge and type(restored.reported_usage[1].input_tokens) is int, "call identities and reported integer usage exceed binary64 integer precision without narrowing"
    assert [role.name for role in restored.design.roles]==["reviewer","coder"] and restored.design.calls[0].private_notes==(note,), "role order and private payload remain distinct from addressed messages"
    assert restored.reported_usage[0].input_tokens==0 and restored.reported_usage[0].output_tokens is None, "unknown usage and measured zero remain separate report values"
    replaced=replace(snapshot,task="",reported_usage=(),unit_cost=-0.0)
    store.save(replaced)
    assert store.load()==replaced and store.load().unit_cost.hex()==(-0.0).hex(), "successful snapshot replacement retains empty values and signed-zero metadata"
    messages=(replace(message,content="  facts\r\n世界 \t"),replace(message,sender="requirements",content="",facts=(Fact("extra","additional"),)),replace(message,content="trailing\n"))
    complete=replace(snapshot,design=replace(design,calls=(replace(call,messages=messages),)))
    store.save(complete)
    assert SnapshotStore(path).load()==complete, "same-recipient messages retain multiplicity order and exact original text"

@pytest.mark.skip("Part 3")
def test_loss_aware_fixed_comparison(tmp_path):
    """Account role peaks, required summary losses and fixed-design tradeoffs."""
    multi=design_fixture();receipts=prepare_design(multi)
    assert role_peak_context(receipts)=={"coder":10,"reviewer":4}, "a role's context is its largest complete call rather than lifetime usage"
    assert sum_branch_usage([row.usage for row in receipts])["total_tokens"]==15, "context peaks and total token usage describe different quantities"
    boundaries=(Boundary("first","coder",("z","a","optional"),("a",),("z","a","z")),Boundary("second","reviewer",("safe","extra"),("safe",),("safe",)))
    assert boundary_fact_losses(boundaries)==[{"boundary":"first","role":"coder","lost":("z",)},{"boundary":"second","role":"reviewer","lost":()}], "only omitted required facts belong to their own declared summary boundary"
    single=FixedDesign("single",(Role("solo","SYS",19),),(CallSpec(1,"solo","a"*37,(),(),(),"answer",10,6),))
    store=SnapshotStore(tmp_path/"comparison.json");store.save(Snapshot("fixed",multi,(),0.0));loaded=store.load().design
    report=compare_fixed_design(single,loaded)
    assert report["single"]["over_limit"]==("solo",) and report["multi"]["over_limit"]==() and report["delta_tokens"]==-5 and report["prefer_multi"], "comparison uses each role ceiling and reports actual independent-call token difference"
    lossy=replace(multi,boundaries=(Boundary("research-summary","coder",("api","optional"),("optional",),("api",)),))
    blocked=compare_fixed_design(single,lossy)
    assert not blocked["prefer_multi"] and blocked["multi"]["losses"][0]["lost"]==("api",) and blocked["delta_tokens"]==-5, "lower token use cannot excuse a lost required boundary fact"
    costly=FixedDesign("costly",(Role("a","",12),Role("b","",12)),(CallSpec(21,"a","12345678",(),(),(),"one",10,1),CallSpec(22,"b","12345678",(),(),(),"two",10,1)))
    assert compare_fixed_design(single,costly)["prefer_multi"] and compare_fixed_design(single,costly)["delta_tokens"]==4, "a declared context failure can justify a more expensive feasible fixed design"
    assert not compare_fixed_design(replace(single,roles=(Role("solo","SYS",20),)),costly)["prefer_multi"], "a feasible cheaper single design is retained without a declared benefit"
    assert role_peak_context(())=={} and boundary_fact_losses(())==[]

@pytest.mark.skip("Part 4")
def test_completed_stage_csv():
    """Encode stage-owned usage, required losses and failures through a supplied CSV driver."""
    stages=(CompletedStage('run,"一"',4,"coder",Usage(1,"coder",8,3,1),("keep","lost","optional"),("keep",),("lost","keep"),"ok"),CompletedStage("other",9,"coder",None,("missing",),(),("missing",),"failed"),CompletedStage("other",10,"reviewer",Usage(2,"reviewer",0,0,0),(),(),(),"ok"))
    async def exercise():
        state={"pulled":0,"closed":False}
        async def source():
            try:
                for stage in stages:state["pulled"]+=1;yield stage
            finally:state["closed"]=True
        stream=stream_comparisons(source());header=await stream.__anext__()
        assert state["pulled"]==0, "the supplied report header does not consume a completed stage"
        first=await stream.__anext__()
        assert state["pulled"]==1, "the supplied driver publishes the current stage before requesting a future stage"
        raw=header+first+"".join([piece async for piece in stream])
        parser=csv.DictReader(io.StringIO(raw,newline=""));rows=list(parser)
        assert parser.fieldnames==["run","stage","role","input_tokens","output_tokens","lost_fact_ids","status"] and len(rows)==3, "every completed stage including a partial failure has one domain CSV row"
        assert [(r["run"],r["stage"],r["role"]) for r in rows]==[('run,"一"',"4","coder"),("other","9","coder"),("other","10","reviewer")], "stage identities and repeated role calls remain original completion metadata"
        assert [(r["input_tokens"],r["output_tokens"],r["status"]) for r in rows]==[("8","3","ok"),("","","failed"),("0","0","ok")], "stage rows retain their own input output and supplied failure status"
        assert [json.loads(r["lost_fact_ids"]) for r in rows]==[["lost"],["missing"],[]], "stage CSV loss fields contain only that summary's required omissions"
        assert state["closed"], "the supplied CSV source owner closes on exhaustion"
        state.update(pulled=0,closed=False)
        early=stream_comparisons(source());await early.__anext__();await early.__anext__();await early.aclose()
        assert state=={"pulled":1,"closed":True}, "closing the supplied driver does not fabricate another stage"
        async def empty():
            if False:yield stages[0]
        assert list(csv.DictReader(io.StringIO("".join([p async for p in stream_comparisons(empty())]),newline="")))==[], "an empty completed-stage source has no invented comparison row"
    asyncio.run(exercise())

@pytest.mark.skip("Part 5")
def test_nested_context_scope_boundaries():
    """Carry shared facts down a scope tree without leaking sibling private context."""
    roles=(Role("coder","code",99),Role("reviewer","review",99))
    tree=Scope("root",(Fact("task","shared"),),(PrivateNote("reviewer","review root",(Fact("review","only reviewer"),)),),(
        Scope("left",(Fact("branch","left"),),(PrivateNote("coder","left-secret",(Fact("secret","left only"),)),),(Leaf("worker","coder",("task","branch","secret")),Leaf("check","reviewer",("task","branch","secret")))),
        Scope("right",(),(),(Leaf("worker","coder",("task","secret")),)),
    ))
    rows=context_scope_report(tree,roles)
    assert [row["path"] for row in rows]==[("root","left","worker"),("root","left","check"),("root","right","worker")], "each scope leaf retains its full branch path and declared child order"
    assert rows[0]["visible"]==("branch","secret","task") and rows[0]["missing"]==(), "branch-local private facts reach their intended descendant role"
    assert rows[1]["visible"]==("branch","review","task") and rows[1]["missing"]==("secret",), "another role does not acquire a sibling specialist's private facts"
    assert rows[2]["visible"]==("task",) and rows[2]["missing"]==("secret",), "a same-role leaf in another branch cannot inherit its sibling branch context"
    assert context_scope_report(Leaf("alone","coder",("absent",)),roles)==[{"path":("alone",),"role":"coder","visible":(),"missing":("absent",)}], "an isolated leaf reports its own declared missing facts"
    with pytest.raises(ValueError):context_scope_report(Scope("bad",(),(PrivateNote("unknown","x",()),),()),roles)
    assert tree.children[1].shared_facts==() and tree.children[0].private_notes[0].content=="left-secret", "scope traversal preserves caller-owned branch records"
    assert context_scope_report(Scope("empty"),roles)==[], "an accepted empty scope contains no leaf report rows"
