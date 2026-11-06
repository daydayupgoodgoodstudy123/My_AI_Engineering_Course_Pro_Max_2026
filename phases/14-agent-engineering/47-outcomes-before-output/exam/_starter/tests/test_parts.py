import asyncio
import copy
import hashlib
import time
from dataclasses import replace
import pytest
from outcomes.frame import Frame,Constraint,Compatibility,validate,decision
from outcomes.revisions import Revisions
from outcomes.leaks import Phrase,Leak,find_leaks
from outcomes.edits import Edit,workshop
from outcomes.tree import Outcome,Resolved,resolve

ALIASES={"incident assistant":("incident assistant","assistant for incidents")}

def frame():
    return Frame("on-call engineer","production alert","searches dashboards","identifies the affected service",[Constraint("read-only diagnosis")],["automatic remediation"],"incident assistant")

@pytest.mark.skip("Part 1")
def test_outcome_frame():
    """Outcome framing rejects hidden outputs and unfixed technology without losing legitimate constraints."""
    compat=Compatibility([("PostgreSQL","existing audit schema requires it")])
    leaked=frame();leaked.desired_outcome="Uses an ASSISTANT   FOR INCIDENTS"
    assert decision(leaked,compat,ALIASES)['issues']==["desired outcome names the proposed output"], "finite output aliases cannot hide inside an outcome"
    blank=frame();blank.constraints=[Constraint(" \t")];blank.non_goals=["\n"]
    assert validate(blank,compat,ALIASES)==["constraints need nonblank items","non-goals need nonblank items"], "boundary lists must contain usable entries"
    unfixed=frame();unfixed.constraints=[Constraint("Use Rust","Rust")]
    assert decision(unfixed,compat,ALIASES)['issues']==["technology lacks compatibility evidence: Rust"], "another technology's receipt does not fix this choice"
    fixed=frame();fixed.proposed_output="PostgreSQL";fixed.constraints=[Constraint("Keep PostgreSQL audit schema","PostgreSQL")]
    assert validate(fixed,compat,ALIASES)==[], "fixed technology belongs in constraints without becoming outcome leakage"
    missing=frame();missing.user=" "
    assert decision(missing,compat,ALIASES)['next_question'] is None, "no invented user appears in the evidence question"
    entries=[(f"tech-{i}",f"compatibility receipt {i}") for i in range(18000)]
    compat=Compatibility(entries);big=frame();big.constraints=[Constraint("preserve interface",f"tech-{i*13%18000}") for i in range(6000)]
    start=time.perf_counter();issues=validate(big,compat,{});elapsed=time.perf_counter()-start
    assert issues==[]
    assert elapsed<0.05, "compatibility receipts must be indexed instead of rescanned per constraint"
    assert validate(unfixed,Compatibility([("Rust","target ABI requires Rust")]),ALIASES)==[], "compatibility snapshots answer independently"

@pytest.mark.skip("Part 2")
def test_revision_history(tmp_path):
    """Content-addressed revisions preserve full frames and their exact parent history."""
    original=frame();original.current_behavior="ouvre deux onglets\n然后复制\t "
    root=tmp_path/'revisions';store=Revisions(str(root));a=store.save(original)
    assert store.save(original)==a and len(list(root.iterdir()))==1, "equal content and parent reuse an object"
    edited=copy.deepcopy(original);edited.non_goals.append("weekly summary");b=store.save(edited,a)
    fork=store.save(edited)
    assert b!=fork, "parent identity is part of a revision's content"
    reopened=Revisions(str(root));history=reopened.history(b)
    assert [(r.digest,r.parent,r.frame) for r in history]==[(b,a,edited),(a,None,original)], "revision order and every typed frame field survive reopen"
    assert reopened.load(fork).frame==edited
    for path in root.iterdir(): assert path.stem==hashlib.sha256(path.read_bytes()).hexdigest(), "object filenames identify the exact stored bytes"
    loaded=reopened.load(b);loaded.frame.constraints.append(Constraint("scratch"))
    assert reopened.load(b).frame==edited, "loaded revisions do not mutate the stored frame"
    ordered=copy.deepcopy(original);ordered.non_goals=["zeta","alpha","zeta"]
    c=store.save(ordered,b)
    assert store.load(c).frame==ordered, "frame non-goal order and duplicate entries remain exact revision content"
    assert [r.digest for r in store.history(c)]==[c,b,a], "history traverses beyond the immediate parent"
    before=sorted(root.iterdir())
    with pytest.raises(KeyError): store.save(frame(),"missing-parent")
    assert sorted(root.iterdir())==before, "an unknown parent cannot leave an orphan object"
    with pytest.raises(KeyError): store.load("no-object")

PHRASES=[Phrase("vector-short","model","vector"),Phrase("short","infrastructure","database"),Phrase("vector","architecture","vector database"),Phrase("weekly","cadence","weekly AI summary"),Phrase("assistant-z","product","incident assistant"),Phrase("assistant-a","product","incident assistant")]

@pytest.mark.skip("Part 3")
def test_lexical_solution_leakage():
    """Finite leakage phrases use whole normalized tokens and longest original-text spans."""
    text="Deploy VECTOR-databases; keep databasesafe, then weekly AI summaries. Incident assistant!"
    assert find_leaks(text,PHRASES)==[Leak("vector","architecture",7,23),Leak("weekly","cadence",49,68),Leak("assistant-a","product",70,88)], "longest whole-token phrases retain original character spans and deterministic ties"
    assert [text[x.start:x.end] for x in find_leaks(text,PHRASES)]==["VECTOR-databases","weekly AI summaries","Incident assistant"], "normalization does not rewrite the evidence slice"
    assert find_leaks("数据库; vector database",PHRASES)==[Leak("vector","architecture",5,20)], "offsets are Python characters rather than UTF-8 byte positions"
    assert find_leaks("database database",PHRASES)==[Leak("short","infrastructure",0,8),Leak("short","infrastructure",9,17)], "separate occurrences are not deduplicated"
    assert find_leaks("databasesafe",PHRASES)==[] and find_leaks("",PHRASES)==[]

async def edits_source(edits,pulled):
    for edit in edits:pulled.append(edit);yield edit

def collect(gen):
    async def drain():return [x async for x in gen]
    return asyncio.run(drain())

@pytest.mark.skip("Part 4")
def test_workshop_edits():
    """Issue changes follow every edit ordinal without replaying baseline or touching the input frame."""
    initial=frame();initial.user="";initial.desired_outcome="Uses the incident assistant"
    before=copy.deepcopy(initial);compat=Compatibility([])
    edits=[Edit("situation",initial.situation),Edit("user","engineer"),Edit("desired_outcome","finds the affected service"),Edit("constraints",[]),Edit("constraints",[Constraint("Use Rust","Rust")])]
    pulled=[]
    assert collect(workshop(initial,edits_source(edits,pulled),compat,ALIASES))==["@@ edit 2 @@\n- user is empty\n","@@ edit 3 @@\n- desired outcome names the proposed output\n","@@ edit 4 @@\n+ constraints need nonblank items\n","@@ edit 5 @@\n- constraints need nonblank items\n+ technology lacks compatibility evidence: Rust\n"], "quiet edits still count and simultaneous removals and additions share one complete block"
    assert initial==before, "the workshop edits a private frame"
    pulled=[]
    async def first():
        gen=workshop(initial,edits_source(edits,pulled),compat,ALIASES);text=await gen.__anext__();await gen.aclose();return text
    assert asyncio.run(first()).startswith("@@ edit 2 @@") and len(pulled)==2, "emit the current block before pulling future edits"
    with pytest.raises(ValueError):collect(workshop(initial,edits_source([Edit("unknown","")],[]),compat,ALIASES))
    assert collect(workshop(initial,edits_source([],[]),compat,ALIASES))==[]
    with pytest.raises(ValueError,match="unknown frame field"):
        collect(workshop(initial,edits_source([Edit("__dict__",{})],[]),compat,ALIASES))

@pytest.mark.skip("Part 5")
def test_outcome_decomposition():
    """Sub-outcomes inherit users and constraints while preserving ancestor non-goal boundaries."""
    child=Outcome("diagnosis",constraints={"actions":{"read"}},non_goals=("analytics","remediate"),children=[Outcome("explain",user="incident commander")])
    root=Outcome("incident",user="on-call engineer",constraints={"actions":{"read","list"}},non_goals=("remediate",),children=[child,Outcome("lookup",constraints={"sources":{"logs"}})])
    before=copy.deepcopy(root)
    assert resolve(root)==[Resolved("incident","on-call engineer",(("actions",("list","read")),),("remediate",)),Resolved("diagnosis","on-call engineer",(("actions",("read",)),),("remediate","analytics")),Resolved("explain","incident commander",(("actions",("read",)),),("remediate","analytics")),Resolved("lookup","on-call engineer",(("actions",("list","read")),("sources",("logs",))),("remediate",))], "preorder retains local narrowing and nearest-user choices without leaking across siblings"
    assert root==before, "resolving outcome constraints does not modify the source tree"
    widened=copy.deepcopy(root);widened.children[0].constraints['actions'].add('write')
    with pytest.raises(ValueError,match="constraint relaxed"):resolve(widened)
    forbidden=copy.deepcopy(root);forbidden.children[0].children.append(Outcome("remediate"))
    with pytest.raises(ValueError,match="non-goal"):resolve(forbidden)
    with pytest.raises(ValueError,match="no user"):resolve(Outcome("orphan"))
    blank_user=Outcome("root",user="engineer",children=[Outcome("child",user=" \t")])
    assert [r.user for r in resolve(blank_user)]==["engineer","engineer"], "a whitespace-only local user inherits the nearest nonblank ancestor"
