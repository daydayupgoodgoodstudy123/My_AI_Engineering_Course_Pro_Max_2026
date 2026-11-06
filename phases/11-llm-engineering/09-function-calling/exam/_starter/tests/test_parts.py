import asyncio
from copy import deepcopy
import json
import re
from time import perf_counter
import pytest
from localtoolbench.tools import ToolService
from localtoolbench.models import Table,Bound,Plan,Invocation,Probe,Issue
from localtoolbench.kernel import matches_row,execute_bound
from localtoolbench.journal import AuditJournal
from localtoolbench.query import compile_query,query_table
from localtoolbench.report import probe_report
from localtoolbench.inspect import inspect_code

def workload():
    width=1024;count=6000
    schema=tuple(("c"+str(i),"number") for i in range(width))
    rows=tuple(tuple(r%7+c for c in range(width)) for r in range(count))
    table=Table("wide",schema,rows)
    predicates=(Bound(0,">",99999),)+tuple(Bound(i,">=",-1) for i in range(1,width))
    return Plan(table,predicates,(0,width-1))

def parse_tap(raw):
    lines=raw.splitlines();assert lines[0]=="TAP version 13"
    assert re.fullmatch(r"1\.\.\d+(?: # SKIP no probes)?",lines[1])
    records=[];i=2
    while i<len(lines):
        match=re.fullmatch(r"(not ok|ok) (\d+) - (.*)",lines[i]);assert match
        assert lines[i+1]=="  ---" and lines[i+2].startswith("  result: ") and lines[i+3]=="  ..."
        records.append((int(match[2]),match[1]=="ok",match[3],json.loads(lines[i+2][10:])));i+=4
    return records

@pytest.mark.skip("Part 1")
def test_local_dispatch_and_bound_scan():
    """Preserve registered callable ownership, weather fixtures and pure conjunctive query execution."""
    service=ToolService();original=deepcopy(service.weather_rows)
    first=service.call("weather",{"city":"Tokyo"})
    assert first=={"city":"Tokyo","temp_c":18,"condition":"cloudy"}, "the registered weather tool produces its own declared result"
    converted=service.call("weather",{"city":"Tokyo","units":"fahrenheit"})
    assert converted["temp_f"]==64.4 and service.weather_rows==original, "weather conversion preserves the shared Celsius fixture for later calls"
    assert service.call("weather",{"city":"Tokyo"})["temp_c"]==18 and service.call("search",{"query":"tools"})["results"]==["Function calling guide"], "successive calls retain their own handler and unmodified source data"
    assert service.call("weather",{"city":"Mars"})=={"error":True,"code":"CITY_NOT_FOUND"} and service.call("missing",{})["code"]=="UNKNOWN_TOOL", "unknown local data and unknown tool names retain their structured failure"
    file=service.call("read_file",{"path":"资料.md"})
    assert file["content"]=="温度\r\n例" and file["size_bytes"]==len(file["content"].encode("utf-8")), "the supplied in-memory file helper retains its exact content and byte metadata"
    table=Table("tiny",(("x","number"),("y","number")),((1,5),(2,3),(3,1)))
    plan=Plan(table,(Bound(0,">",1),Bound(1,"<",3)),(1,0))
    assert execute_bound(plan)==[{"y":1,"x":3}], "conjunctive execution preserves all conditions, row order and declared projection"
    assert matches_row((1,2),()) and matches_row((1,2),(Bound(0,"=",1),Bound(1,"=",2))) and not matches_row((1,2),(Bound(0,"=",1),Bound(1,"=",3))), "empty and all-true conjunctions remain matches while a later false comparison rejects the row"
    with pytest.raises(ValueError):execute_bound(Plan(table,(Bound(0,"<",-1),Bound(99,"=",0)),(0,)))
    empty=Table("empty",table.schema,())
    with pytest.raises(ValueError):execute_bound(Plan(empty,(Bound(0,"=",True),),(0,)))
    wide=workload();started=perf_counter();rows=execute_bound(wide);elapsed=perf_counter()-started
    assert elapsed<0.035, "wide local table requests should stay responsive"
    assert rows==[] and len(wide.table.rows)==6000 and wide.table.rows[-1][-1]==1023+5999%7, "a selective request retains its complete real table and exact empty result"

@pytest.mark.skip("Part 2")
def test_invocation_audit_journal(tmp_path):
    """Persist owned invocation snapshots in append order with exact nested arguments and microseconds."""
    path=tmp_path/"audit.log";journal=AuditJournal(path)
    args={"terms":["b","a"],"enabled":False,"nested":{"note":"line\u2028break\u0085tail"}}
    result={"ok":True,"rows":[2,1]};one=Invocation(8,"query_table",args,result,1000003)
    expected=deepcopy(one);journal.append(one)
    args["terms"].reverse();result["rows"].append(99)
    failed=Invocation(3,"weather",{"city":"Mars"},{"error":True,"code":"CITY_NOT_FOUND"},0)
    journal.append(failed);journal.flush()
    assert AuditJournal(path).replay()==[expected,failed], "reopening retains every invocation's original nested arguments, result and integer microseconds in append order"
    later=Invocation(9,"query_table",{"terms":["a","b"],"enabled":False,"nested":{"note":"line\u2028break\u0085tail"}},{"ok":True,"rows":[2,1]},17)
    reopened=AuditJournal(path);reopened.append(later);reopened.flush();reopened.flush()
    assert reopened.replay()==[expected,failed,later], "a later append retains earlier failures and distinguishes different ordered argument lists without duplicate flush records"
    replayed=reopened.replay();replayed[0].arguments["terms"].clear()
    assert AuditJournal(path).replay()[0]==expected, "replay callers cannot rewrite the persisted invocation history"
    blank=AuditJournal(tmp_path/"blank.log");blank.flush()
    assert blank.replay()==[], "an empty flushed journal reopens without fabricated invocations"
    repeated=AuditJournal(tmp_path/"repeated.log")
    calls=[Invocation(10,"weather",{"city":"Tokyo"},{"temp_c":18},1),Invocation(11,"weather",{"city":"Tokyo"},{"temp_c":18},2)]
    for call in calls:repeated.append(call)
    repeated.flush()
    assert repeated.replay()==calls, "distinct invocations with matching tools and arguments remain separate records"

@pytest.mark.skip("Part 3")
def test_allowlisted_typed_query_compiler():
    """Compile full table/field/operator/type/projection policy before repaired bound execution."""
    public=Table("public",(("name","string"),("score","number"),("active","boolean")),(("z",2,True),("a",3,False),("m",2,True)))
    secret=Table("secret",public.schema,(("hidden",99,True),));empty=Table("empty",public.schema,())
    catalog={"public":public,"secret":secret,"empty":empty};allowed={"public","empty"}
    spec={"table":"public","filters":[{"field":"score","op":">=","value":2},{"field":"active","op":"=","value":True}],"projection":["score","name"]}
    before=deepcopy(spec);plan=compile_query(spec,catalog,allowed)
    assert plan.table is public and [b.index for b in plan.predicates]==[1,2] and plan.projection==(1,0), "the compiled plan binds each field and projection to the selected table's own schema"
    assert query_table(spec,catalog,allowed)==[{"score":2,"name":"z"},{"score":2,"name":"m"}] and spec==before, "typed query execution preserves matching source row order, requested fields and caller input"
    assert list(query_table(spec,catalog,allowed)[0])==["score","name"], "projection fields retain their declared order rather than schema or alphabetical order"
    for table in ("secret","unknown"):
        with pytest.raises(ValueError):query_table({**spec,"table":table},catalog,allowed)
    for op,expected in ((">",[{"name":"a","score":3,"active":False}]),("<",[]),("<=",[{"name":"z","score":2,"active":True},{"name":"m","score":2,"active":True}]),("=",[{"name":"z","score":2,"active":True},{"name":"m","score":2,"active":True}])):
        assert query_table({"table":"public","filters":[{"field":"score","op":op,"value":2}]},catalog,allowed)==expected, "operator binding retains strict and inclusive numeric boundaries without coercion"
    for condition in ({"field":"score","op":"=","value":"2"},{"field":"score","op":"=","value":True},{"field":"active","op":">","value":False},{"field":"missing","op":"=","value":1},{"field":"score","op":"!=","value":2}):
        for table in ("public","empty"):
            with pytest.raises(ValueError):compile_query({"table":table,"filters":[{"field":"score","op":"<","value":-100},condition]},catalog,allowed)
            with pytest.raises(ValueError):query_table({"table":table,"filters":[{"field":"score","op":"<","value":-100},condition]},catalog,allowed)
    for projection in (["missing"],["name","name"]):
        with pytest.raises(ValueError):query_table({"table":"empty","filters":[],"projection":projection},catalog,allowed)
    assert query_table({"table":"public","filters":[],"projection":[]},catalog,allowed)==[{},{},{}], "an explicitly empty projection differs from an omitted full-row projection"
    assert query_table({"table":"public","filters":[{"field":"name","op":">","value":"m"}],"projection":["name"]},catalog,allowed)==[{"name":"z"}], "string ordering is bound to the declared string field"
    reordered=Table("reordered",(("score","number"),("bonus","number"),("name","string"),("active","boolean")),((4,1,"r",True),(2,9,"s",False)))
    selected={"table":"reordered","filters":[{"field":"score","op":">=","value":4}],"projection":["name","score"]}
    assert query_table(selected,{**catalog,"reordered":reordered},allowed|{"reordered"})==[{"name":"r","score":4}], "each allowed table query retains that table's own field bindings and requested output"

@pytest.mark.skip("Part 4")
def test_completed_tool_probe_tap():
    """Emit the finite TAP subset in completion order with original probe numbering and failures."""
    async def exercise():
        gate=asyncio.Event();state={"slow_closed":False}
        async def slow():
            try:await gate.wait();return {"error":True,"code":"CITY_NOT_FOUND"}
            finally:state["slow_closed"]=True
        async def quick():return 0
        async def broken():raise ValueError("fixture failure")
        probes=[Probe(1,"weather东京",slow),Probe(2,"numeric-zero",quick),Probe(3,"broken",broken)]
        stream=probe_report(probes);header=await stream.__anext__()
        assert header=="TAP version 13\n1..3\n", "the probe plan declares every original probe before result records"
        first=await asyncio.wait_for(stream.__anext__(),.5)
        early=parse_tap(header+first)
        assert len(early)==1 and early[0][0] in (2,3) and not gate.is_set() and not state["slow_closed"], "a completed tool probe becomes observable while an earlier declared probe is still pending"
        gate.set();raw=header+first+"".join([piece async for piece in stream]);records=parse_tap(raw);by_number={number:(ok,label,result) for number,ok,label,result in records}
        assert sorted(by_number)==[1,2,3] and records[-1][0]==1, "completion order preserves the original declared probe numbers rather than renumbering results"
        assert by_number[1]==(False,"weather东京",{"error":True,"code":"CITY_NOT_FOUND"}) and by_number[2]==(True,"numeric-zero",0) and by_number[3]==(False,"broken",{"error":True,"message":"fixture failure"}), "structured failures and raised tool errors are failed probes while a zero-valued success remains successful"
        gate.clear();state["slow_closed"]=False;early_stream=probe_report(probes);await early_stream.__anext__();await early_stream.__anext__();await early_stream.aclose()
        assert state["slow_closed"], "client closure cancels and closes unfinished local probes"
        assert parse_tap("".join([piece async for piece in probe_report([])]))==[], "an empty declared probe set emits its valid empty plan"
        async def explicit_success():return {"error":False,"payload":[]}
        labeled="".join([piece async for piece in probe_report([Probe(1,"MiXeD label",explicit_success)])])
        assert parse_tap(labeled)==[(1,True,"MiXeD label",{"error":False,"payload":[]})], "successful structured outcomes retain their original probe label and diagnostic result"
    asyncio.run(exercise())

@pytest.mark.skip("Part 5")
def test_recursive_syntax_audit():
    """Inspect every nested AST node without executing code or treating text as syntax."""
    code="def fn():\n    if True:\n        import os\n        x=thing.__class__.__base__\n        y=eval('1')\n    return 'import os'\nfrom math import sqrt\n"
    prefix=("body",0,"body",0,"body")
    expected=[Issue("import",prefix+(0,),3,8),Issue("dunder",prefix+(1,"value"),4,10),Issue("dunder",prefix+(1,"value","value"),4,10),Issue("unsafe_name",prefix+(2,"value","func"),5,10),Issue("import",("body",1),7,0)]
    assert inspect_code(code)==expected, "all nested syntax violations retain preorder node paths and native AST positions"
    assert inspect_code("# import os; eval()\nx='open import __class__'\ny=obj.__private\n")==[], "comments, strings and a non-dunder attribute are not forbidden syntax nodes"
    assert inspect_code("open=3")==[Issue("unsafe_name",("body",0,"targets",0),1,0)], "the source unsafe-name policy covers binding contexts as well as call sites"
    assert inspect_code("raise RuntimeError('must stay inert')")==[] and inspect_code("")==[], "submitted code is inspected without execution and empty syntax has no violations"
    with pytest.raises(SyntaxError):inspect_code("if:")
    assert inspect_code("π = 1; eval('x')")==[Issue("unsafe_name",("body",1,"value","func"),1,8)], "syntax diagnostics retain native AST columns after non-ASCII source text"
    assert inspect_code("x = {open: eval, globals: exec}")==[Issue("unsafe_name",("body",0,"value","keys",0),1,5),Issue("unsafe_name",("body",0,"value","keys",1),1,17),Issue("unsafe_name",("body",0,"value","values",0),1,11),Issue("unsafe_name",("body",0,"value","values",1),1,26)], "syntax diagnostics follow declared AST field preorder even when source positions interleave"
