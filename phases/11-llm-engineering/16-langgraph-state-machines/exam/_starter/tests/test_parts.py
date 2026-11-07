"""Five local historical-fork, persistence, barrier, patch and lineage stages."""
import asyncio,copy,json,time
from dataclasses import replace
import pytest
from forkgraph.contracts import Checkpoint,ForkRequest,Worker,CommittedStep,write_artifact
from forkgraph.memory import fork_and_trace
from forkgraph.checkpoints import FileCheckpointer
from forkgraph.superstep import run_superstep
from forkgraph.patch_driver import publish_commits
from forkgraph.lineage import compare_branches

def checkpoint(thread,name,parent=None,branch="main",state=None):
    reducers={"messages":"append","pending":"overwrite","budget":"overwrite","trace/~":"append"}
    value={"messages":[{"role":"user","content":name}],"pending":{"tools":{"value":7,"meta":{"scope":"safe"}}},"budget":100,"trace/~":[]}
    return Checkpoint(thread,name,parent,branch,"tools",1,value if state is None else state,reducers)
def deep_history(n=18000):
    return tuple(checkpoint("deep","c"+str(i),"c"+str(i-1) if i else None,state={"messages":[{"step":i}],"pending":{"tools":{"value":i}},"budget":100,"trace/~":[]}) for i in range(n))
def consume_deep(result,records,calls):
    n=len(records)
    assert len(result.records)==n+1 and len(result.ancestry)==n+1 and calls==[n-1],"deep fork reports retain every checkpoint and execute only the selected local action"
    for i,row in enumerate(result.ancestry[:-1]):
        assert (row.thread_id,row.checkpoint_id,row.parent_id,row.branch_id,row.next_node,row.schema_version,row.state,row.reducers)==("deep","c"+str(i),"c"+str(i-1) if i else None,"main","tools",1,{"messages":[{"step":i}],"pending":{"tools":{"value":i}},"budget":100,"trace/~":[]},{"messages":"append","pending":"overwrite","budget":"overwrite","trace/~":"append"}),"deep fork ancestry preserves complete ordered immutable source snapshots"
    last=result.checkpoint
    assert result.records[:-1]==records and result.ancestry[-1]==last and (last.thread_id,last.checkpoint_id,last.parent_id,last.branch_id,last.next_node,last.schema_version,last.state)==("deep","fork","c"+str(n-1),"new","END",1,{"messages":[{"step":n-1},{"result":n-1}],"pending":{},"budget":0,"trace/~":[]}),"deep fork results preserve selected parent and complete new branch state"

def apply_patch(state,operations):
    value=copy.deepcopy(state)
    for op in operations:
        parts=[x.replace("~1","/").replace("~0","~") for x in op["path"].split("/")[1:]]
        if len(parts)==2:
            assert op["op"]=="add" and parts[1]=="-";value[parts[0]].append(op["value"])
        else:
            assert len(parts)==1 and op["op"] in ("add","replace")
            if op["op"]=="replace":assert parts[0] in value
            value[parts[0]]=op["value"]
    return value

@pytest.mark.skip("Part 1")
def test_historical_fork_and_complete_ancestry():
    """Explicit historical snapshots, independent forks, list reducers and responsive ancestry."""
    old=checkpoint("t","old");latest=replace(checkpoint("t","latest","old",state={"messages":[{"role":"assistant","content":"done"}],"pending":{},"budget":0,"trace/~":[]}),next_node="END");records=(old,latest);before=copy.deepcopy(records);calls=[]
    def action(payload):
        calls.append(payload["value"]);payload["meta"]["scope"]="consumed"
        return {"messages":[{"role":"tool","content":"7"},{"role":"tool","content":"7"}],"budget":99}
    result=fork_and_trace(records,ForkRequest("t","old","fork-a","A","tools"),{"tools":action})
    assert records==before,"advancing a fork cannot mutate any nested source checkpoint"
    assert result.checkpoint.state["messages"]==before[0].state["messages"]+[{"role":"tool","content":"7"},{"role":"tool","content":"7"}],"the declared append reducer retains existing and duplicate new messages"
    assert (result.checkpoint.parent_id,result.checkpoint.branch_id,result.checkpoint.state["pending"],result.checkpoint.state["budget"])==("old","A",{},99),"a fork advances only the explicitly selected historical parent"
    assert tuple(x.checkpoint_id for x in result.ancestry)==("old","fork-a") and calls==[7],"fork ancestry follows parent links rather than replaying later unrelated checkpoints"
    sibling=fork_and_trace(result.records,ForkRequest("t","old","fork-b","B","tools"),{"tools":action})
    assert result.checkpoint.state==sibling.checkpoint.state and result.checkpoint.branch_id!=sibling.checkpoint.branch_id and result.records[0]==before[0],"sibling branches independently advance the same immutable old state"
    with pytest.raises(KeyError):fork_and_trace(records,ForkRequest("t","unknown","absent","X","tools"),{"tools":action})
    records=deep_history();calls=[]
    def deep_action(payload):calls.append(payload["value"]);return {"messages":[{"result":payload["value"]}],"budget":0}
    started=time.perf_counter();large=fork_and_trace(records,ForkRequest("deep",records[-1].checkpoint_id,"fork","new","tools"),{"tools":deep_action});consume_deep(large,records,calls);elapsed=time.perf_counter()-started
    assert elapsed<0.2,"deep historical fork reports should stay responsive"

@pytest.mark.skip("Part 2")
def test_immutable_checkpoint_artifacts(tmp_path):
    """Complete scoped snapshots, idempotent retries and no dangling published index on failure."""
    root=checkpoint("project:a","root");child=checkpoint("project:a","next","root","fork",state={"messages":[{"role":"tool","content":"原\n\u2028文"},{"role":"tool","content":"原\n\u2028文"}],"pending":{"review":{"big":2**60+1}},"budget":37,"trace/~":["x"]});other=checkpoint("project:b","root")
    store=FileCheckpointer(tmp_path/"db")
    for row in (root,child,other):store.save(row)
    assert FileCheckpointer(tmp_path/"db").load_all()==(root,child,other),"reopened lineage keeps complete state metadata scoped identities and commit order"
    store.save(child)
    assert store.load_all()==(root,child,other),"an identical checkpoint retry cannot append another lineage occurrence"
    with pytest.raises(ValueError,match="immutable"):store.save(replace(child,branch_id="rewritten"))
    with pytest.raises(ValueError,match="missing scoped parent"):store.save(checkpoint("project:b","child","next"))
    def fail_write(path,row):raise OSError("injected local artifact failure")
    failed=FileCheckpointer(tmp_path/"db",writer=fail_write)
    with pytest.raises(OSError,match="injected"):failed.save(checkpoint("project:a","failed","next","failure"))
    assert FileCheckpointer(tmp_path/"db").load_all()==(root,child,other),"a failed snapshot write cannot publish a dangling lineage index entry"
    assert FileCheckpointer(tmp_path/"empty").load_all()==(),"an absent checkpointer has no committed snapshots"
    from forkgraph.contracts import artifact_path
    orphan=checkpoint("project:a","unindexed","next","orphan")
    write_artifact(artifact_path(tmp_path/"db",(orphan.thread_id,orphan.checkpoint_id)),orphan)
    assert store.load_all()==(root,child,other),"unindexed artifacts are not committed lineage records"
    identity_root=tmp_path/"identity";identity_store=FileCheckpointer(identity_root);identity_store.save(root)
    write_artifact(artifact_path(identity_root,(root.thread_id,root.checkpoint_id)),replace(root,thread_id="project:wrong"))
    with pytest.raises(ValueError,match="artifact index identity"):identity_store.load_all()

@pytest.mark.skip("Part 3")
def test_send_superstep_barrier_and_reducers():
    """Common independent pre-state, declaration-order reduction and overwrite conflict refusal."""
    state={"messages":[{"seed":1}],"pending":{"tag":"original"},"budget":10,"trace/~":[]};original=copy.deepcopy(state);seen=[]
    reducers={"messages":"append","pending":"overwrite","budget":"overwrite","trace/~":"append"}
    def first(value):
        seen.append(("first",len(value["messages"]),value["pending"]["tag"]));value["pending"]["tag"]="local"
        return {"messages":[{"worker":"first"}],"trace/~":["A"]}
    def second(value):seen.append(("second",len(value["messages"]),value["pending"]["tag"]));return {"messages":[{"worker":"second"}],"budget":9,"trace/~":["B","B"]}
    result=run_superstep(state,reducers,(Worker("first",first),Worker("second",second)),("second","first"))
    assert seen==[("second",1,"original"),("first",1,"original")] and state==original,"every worker reads only its independent common pre-step snapshot"
    assert result.state=={"messages":[{"seed":1},{"worker":"first"},{"worker":"second"}],"pending":{"tag":"original"},"budget":9,"trace/~":["A","B","B"]},"a committed superstep reduces all worker deltas in declaration order"
    assert tuple(name for name,delta in result.worker_updates)==("first","second") and result.completion_order==("second","first"),"declaration evidence and actual completion order remain distinct"
    with pytest.raises(ValueError,match="parallel overwrite conflict"):run_superstep(state,reducers,(Worker("a",lambda s:{"budget":3}),Worker("b",lambda s:{"budget":3})),("a","b"))
    assert state==original,"a rejected parallel overwrite cannot mutate the caller snapshot"
    empty=run_superstep(state,reducers,(),())
    assert empty.state==state and empty.worker_updates==(),"an empty Send batch preserves the complete pre-state"
    with pytest.raises(ValueError,match="worker order"):run_superstep(state,reducers,(Worker("a",lambda s:{}),),("missing",))
    with pytest.raises(ValueError,match="worker order"):run_superstep(state,reducers,(Worker("a",lambda s:{}),),("a","a"))

@pytest.mark.skip("Part 4")
def test_committed_json_patch_stream():
    """Exact-parent complete superstep patches, JSON Pointer segments and append duplicates."""
    class Feed:
        def __init__(self,rows):self.rows=iter(rows);self.pulled=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            try:value=next(self.rows)
            except StopIteration:raise StopAsyncIteration
            self.pulled+=1;return value
        async def aclose(self):self.closed=True
    async def check():
        parent=checkpoint("t","parent",state={"messages":["old"],"pending":{},"budget":10,"trace/~":["seed"]})
        state={"messages":["old","new","new"],"pending":{},"budget":8,"trace/~":["seed","a/b~c"]}
        child=replace(parent,checkpoint_id="child",parent_id="parent",branch_id="fork",state=state,next_node="END")
        event=CommittedStep(parent,child,(("worker-a",{"messages":["new"]}),("worker-b",{"messages":["new"],"budget":8,"trace/~":["a/b~c"]})))
        second=replace(child,checkpoint_id="second",parent_id="child",state={**state,"budget":7})
        feed=Feed((event,CommittedStep(child,second,(("only",{"budget":7}),))));stream=publish_commits(feed);first=json.loads(await stream.__anext__())
        assert feed.pulled==1 and (first["thread_id"],first["checkpoint_id"],first["parent_id"])==("t","child","parent"),"each completed patch belongs to its actual committed checkpoint and parent"
        assert first["patch"]==[{"op":"add","path":"/messages/-","value":"new"},{"op":"add","path":"/messages/-","value":"new"},{"op":"replace","path":"/budget","value":8},{"op":"add","path":"/trace~1~0/-","value":"a/b~c"}],"patch operations preserve pointer field identity append order and unchanged parent values"
        assert apply_patch(parent.state,first["patch"])==state,"one published patch transforms the exact parent into the entire committed superstep state"
        tail=[json.loads(x) async for x in stream]
        assert len(tail)==1 and tail[0]["parent_id"]=="child" and apply_patch(child.state,tail[0]["patch"])==second.state,"each later patch compares against its own complete committed parent"
        assert feed.closed,"the supplied patch driver closes its completed source"
        early=Feed((event,event));stream=publish_commits(early);await stream.__anext__();await stream.aclose()
        assert early.pulled==1 and early.closed,"closing after one complete patch does not consume later commits"
        empty=Feed(());assert [x async for x in publish_commits(empty)]==[] and empty.closed,"an empty committed source emits no synthetic state patch"
        add_parent=replace(parent,checkpoint_id="add-parent",state={"messages":[]},reducers={"messages":"append","new~/":"overwrite"})
        add_child=replace(add_parent,checkpoint_id="add-child",parent_id="add-parent",state={"messages":[],"new~/":0})
        added=[json.loads(x) async for x in publish_commits(Feed((CommittedStep(add_parent,add_child,()),)))]
        assert added[0]["patch"]==[{"op":"add","path":"/new~0~1","value":0}] and apply_patch(add_parent.state,added[0]["patch"])==add_child.state,"a new committed field uses add with its complete escaped field identity"
        replace_parent=replace(parent,checkpoint_id="replace-parent",state={"messages":["old"]},reducers={"messages":"append"})
        replace_child=replace(replace_parent,checkpoint_id="replace-child",parent_id="replace-parent",state={"messages":["changed","tail"]})
        replaced=[json.loads(x) async for x in publish_commits(Feed((CommittedStep(replace_parent,replace_child,()),)))]
        assert replaced[0]["patch"]==[{"op":"replace","path":"/messages","value":["changed","tail"]}] and apply_patch(replace_parent.state,replaced[0]["patch"])==replace_child.state,"a changed append prefix requires replacement of the complete committed list"
    asyncio.run(check())

@pytest.mark.skip("Part 5")
def test_thread_scoped_branch_divergence():
    """Nearest shared ancestor, independent thread spellings and complete branch suffix evidence."""
    foreign=(checkpoint("other","root"),checkpoint("other","middle","root"),checkpoint("other","left","middle"),checkpoint("other","right","middle"))
    local=(checkpoint("t","root"),checkpoint("t","middle","root"),checkpoint("t","left","middle","L"),checkpoint("t","right","middle","R"),checkpoint("t","left2","left","L"),checkpoint("t","solo",None,"S"))
    result=compare_branches(foreign+local,"t","left2","right")
    assert result.common_id=="middle" and result.thread_id=="t","branch divergence identifies the nearest actual common ancestor in the selected thread"
    assert result.left_path==(local[0],local[1],local[2],local[4]) and result.right_path==(local[0],local[1],local[3]),"complete lineage paths retain the selected thread snapshots and real parent edges"
    assert result.left_suffix==(local[2],local[4]) and result.right_suffix==(local[3],),"divergence suffixes exclude the shared ancestor and retain full branch order"
    same=compare_branches(foreign+local,"t","left","left2")
    assert same.common_id=="left" and same.left_suffix==() and same.right_suffix==(local[4],),"an ancestor head is a valid common point with an empty branch suffix"
    separate=compare_branches(foreign+local,"t","solo","right")
    assert separate.common_id is None and separate.left_suffix==(local[5],) and separate.right_suffix==separate.right_path,"disconnected roots preserve both complete paths without inventing a shared commit"
    cyclic=(checkpoint("t","a","b"),checkpoint("t","b","a"))
    with pytest.raises(ValueError,match="checkpoint cycle"):compare_branches(cyclic,"t","a","b")
    identical=compare_branches(foreign+local,"t","left2","left2")
    assert identical.common_id=="left2" and identical.left_path==result.left_path and identical.right_path==result.left_path and identical.left_suffix==identical.right_suffix==(),"identical branch heads share their complete path with no divergent suffix"
    labels=(checkpoint("labels","root",branch="shared"),checkpoint("labels","a","root","shared"),checkpoint("labels","b","root","shared"))
    labeled=compare_branches(labels,"labels","a","b")
    assert labeled.common_id=="root" and labeled.left_suffix==(labels[1],) and labeled.right_suffix==(labels[2],),"branch labels do not replace checkpoint identities along real parent paths"
