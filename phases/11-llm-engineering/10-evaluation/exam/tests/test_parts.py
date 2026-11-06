import asyncio,csv,json,time
import xml.etree.ElementTree as ET
import pytest
from evalpair.records import EvalCase,EvalScore
from evalpair.service import EvalService
from evalpair.metrics import rouge_l_score
from evalpair.contracts import Observation,RunMeta,Interval,Comparison,CaseSpec,CategorySpec,SuiteSpec
from evalpair.bank import EvalBank
from evalpair.bootstrap import compare_paired
from evalpair.completion_driver import CompletedCase,EvalJob
from evalpair.junit import evaluation_report
from evalpair.coverage import coverage_tree

def observation(case,category,criterion,score,**changes):
    values=dict(case_id=case,category=category,criterion=criterion,input_text="question",model_output="answer",reference_output="reference",score_text=score,reasoning="fixture")
    values.update(changes);return Observation(**values)

@pytest.mark.skip("Part 1")
def test_typed_judge_and_sequence_metric():
    """Repair typed judge assembly, source mean and ordered ROUGE-L scoring."""
    scores={"relevance":EvalScore("relevance",4,"Relevant fixture",7),"correctness":EvalScore("correctness",5,"Correct fixture",5)}
    judge=lambda case,output,criterion:scores.get(criterion,EvalScore(criterion,3,"default fixture"))
    case=EvalCase("q1","question","alpha beta gamma","factual")
    result=EvalService().evaluate(case,"gamma beta alpha",judge,["relevance","correctness"])
    assert result["rouge_l"]==0.3333, "ROUGE-L distinguishes token order even when the vocabulary is identical"
    assert result["average"]==4.5, "a fractional judge-score mean remains fractional"
    assert result["result"].scores==(scores["relevance"],scores["correctness"]), "the in-memory result retains complete typed scores in the requested rubric order"
    assert rouge_l_score("a a b","a a b")==1.0 and rouge_l_score("a b c","a c")==0.8, "ordered repeated-token matches retain their full subsequence contribution"
    assert rouge_l_score("ALPHA beta","alpha BETA")==1.0 and rouge_l_score("a, b","a b")==0.5, "the source metric lowercases split tokens while retaining punctuation"
    assert all(rouge_l_score(ref,out)==0.0 for ref,out in [(None,"answer"),("","answer"),("  ","answer"),("reference","")]), "missing or empty references and empty outputs have the declared zero metric"
    no_scores=EvalService().evaluate(case,"answer",lambda *args:(_ for _ in ()).throw(AssertionError("no judge requested")),[])
    assert no_scores["average"]==0.0 and no_scores["result"].scores==(), "an explicitly empty rubric differs from the default rubric"
    default=EvalService().evaluate(case,"answer",judge)
    assert [score.criterion for score in default["result"].scores]==["relevance","correctness","helpfulness","safety"], "an omitted rubric retains the declared default criterion order"
    wide_ref=" ".join("reference"+str(i) for i in range(13));wide_out=" ".join("hypothesis"+str(i) for i in range(13))
    positive_ref=" ".join(["left"+str(i) for i in range(6)]+["shared"]+["right"+str(i) for i in range(6)])
    positive_out=" ".join(["before"+str(i) for i in range(6)]+["shared"]+["after"+str(i) for i in range(6)])
    start=time.perf_counter();wide=EvalService().evaluate(EvalCase("wide","metric request",wide_ref),wide_out,judge,[])
    positive=EvalService().evaluate(EvalCase("positive","metric request",positive_ref),positive_out,judge,[]);elapsed=time.perf_counter()-start
    assert wide["rouge_l"]==0.0 and wide["result"].model_output==wide_out, "a complete disjoint sequence request retains its declared output and metric"
    assert positive["rouge_l"]==0.0769 and positive["result"].model_output==positive_out, "a shared interior token retains its positive ordered metric and full output"
    assert elapsed<0.08, "moderate evaluation sequences should stay responsive"

@pytest.mark.skip("Part 2")
def test_immutable_evaluation_bank(tmp_path):
    """Store exact CSV observations and independent immutable run metadata."""
    meta=RunMeta("fixture-model","prompt,\"v1\"",0,"notes\r\n中文")
    rows=[observation("b","technical","correctness","4.5000000000000001",input_text="input,\"quote\"\nnext",model_output="<answer>\r\nline\u2028tail",reference_output="",reasoning="why,\"yes\"\nline"),observation("a","safety","safety","0",reference_output=None),observation("c","factual","correctness",None,reference_output="reference")]
    EvalBank(tmp_path).save_run("baseline",meta,rows)
    restored_meta,restored=EvalBank(tmp_path).load_run("baseline")
    assert restored_meta==meta and restored==rows, "reopening retains raw text, exact score spellings, optional references, missing judges and observation order"
    with (tmp_path/"baseline"/"observations.csv").open(encoding="utf-8",newline="") as handle:parsed=list(csv.reader(handle))
    assert len(parsed)==len(rows)+1 and parsed[1][4]==rows[0].model_output, "quoted multiline outputs belong to one complete observation record"
    with pytest.raises(FileExistsError):EvalBank(tmp_path).save_run("baseline",meta,[])
    variant_meta=RunMeta("other","v2",17,"independent")
    EvalBank(tmp_path).save_run("variant",variant_meta,[observation("b","technical","correctness","5")])
    assert EvalBank(tmp_path).load_run("baseline")== (meta,rows) and EvalBank(tmp_path).load_run("variant")[0]==variant_meta, "separate immutable runs retain their own prompt metadata and observations"
    EvalBank(tmp_path).save_run("empty",meta,[])
    assert EvalBank(tmp_path).load_run("empty")== (meta,[]), "an empty observed run reopens without fabricated scores"
    huge_meta=RunMeta("fixture-model","large-seed",9007199254740993,"exact integer metadata")
    EvalBank(tmp_path).save_run("large-seed",huge_meta,[])
    assert EvalBank(tmp_path).load_run("large-seed")[0]==huge_meta, "run metadata retains exact large integer seeds"
    raw_rows=[observation("spaces","technical","correctness","1.00",input_text=" \tquestion\r\n ",model_output=" \tanswer\n ",reference_output=" ref ",reasoning=" why ")]
    EvalBank(tmp_path).save_run("raw-text",meta,raw_rows)
    assert EvalBank(tmp_path).load_run("raw-text")[1]==raw_rows, "raw observation text retains leading and trailing whitespace"

@pytest.mark.skip("Part 3")
def test_paired_stratified_bootstrap():
    """Pair exact case/criterion keys, bootstrap case deltas and retain category evidence."""
    baseline=[observation(case,"technical" if case!="c" else "factual",criterion,str(value)) for case,value in [("b",1),("a",2),("c",3)] for criterion in ["correctness","helpfulness"]]
    variant=[observation(row.case_id,row.category,row.criterion,str(int(row.score_text)+1)) for row in reversed(baseline)]
    report=compare_paired(baseline,variant,samples=31,seed=7)
    assert report.overall==Interval(3,1.0,1.0,1.0) and all(interval.mean==interval.lower==interval.upper==1 for interval in report.criteria.values()), "case-paired constant improvements have exact intervals despite different run order and variable absolute scores"
    assert report.categories["technical"].count==2 and report.criteria["correctness"].count==3 and report.accepted, "category sampling counts cases while criterion sampling retains its own case count"
    before=[observation("many"+str(i),"technical","correctness","0") for i in range(5)]+[observation("risk","safety","correctness","5")]
    after=[observation("many"+str(i),"technical","correctness","3") for i in range(5)]+[observation("risk","safety","correctness","1")]
    hidden=compare_paired(before,after,samples=101,seed=11,tolerance=0.2)
    assert hidden.overall.mean>0 and hidden.categories["safety"]==Interval(1,-4.0,-4.0,-4.0) and not hidden.accepted, "a favorable overall change retains and blocks on a conclusively regressed category"
    unequal_b=[observation("two","technical",criterion,"0") for criterion in ["correctness","helpfulness"]]+[observation("one","technical","correctness","0")]
    unequal_v=[observation("two","technical",criterion,"0") for criterion in ["correctness","helpfulness"]]+[observation("one","technical","correctness","3")]
    unequal=compare_paired(unequal_b,unequal_v,samples=17,confidence=0.6,seed=7)
    assert unequal.categories["technical"].count==2 and unequal.categories["technical"].mean==1.5, "each case contributes once to its category even when its rubric contains more criteria"
    assert compare_paired(unequal_b,unequal_v,samples=17,confidence=0.6,seed=7)==unequal, "the same explicit seed and observation set produce a reproducible report"
    for left,right in [(baseline,variant[:-1]),(baseline,[observation(r.case_id,"other",r.criterion,r.score_text) for r in variant]),([observation("x","safety","safety",None)],[observation("x","safety","safety","0")])]:
        with pytest.raises(ValueError):compare_paired(left,right)
    empty=compare_paired([],[],samples=1,seed=0)
    assert empty==Comparison(None,{},{},True), "an empty comparison has no fabricated interval or category decision"
    with pytest.raises(ValueError):compare_paired(baseline,variant,samples=0)
    seeded_zero=compare_paired(unequal_b,unequal_v,samples=3,confidence=0.5,seed=0)
    seeded_one=compare_paired(unequal_b,unequal_v,samples=3,confidence=0.5,seed=1)
    assert seeded_zero.categories["technical"]==Interval(2,1.5,0.0,0.0) and seeded_one.categories["technical"]==Interval(2,1.5,0.0,1.5), "explicit seeds and declared finite-sample endpoints retain their reproducible intervals"
    tiny=compare_paired(unequal_b,unequal_v,samples=3,confidence=0.01,seed=1)
    assert tiny.categories["technical"]==Interval(2,1.5,1.5,1.5), "small sample and confidence choices retain ordered interval endpoints"
    precise=compare_paired([observation("precise","factual","correctness","0")],[observation("precise","factual","correctness","0.0004")],samples=7,seed=3)
    assert precise.criteria["correctness"]==Interval(1,0.0004,0.0004,0.0004), "small paired score changes retain their full interval value"

@pytest.mark.skip("Part 4")
def test_completed_evaluation_junit():
    """Emit completed cases as parseable JUnit XML with distinct judge/error states."""
    async def exercise():
        gate=asyncio.Event();state={"closed":False}
        fast=CompletedCase('case<2&"',"technical&x","<answer>&\r\nnext","ref\"\n<text>",1,True)
        slow=CompletedCase("case1","safety","unsafe",None,1001,False)
        async def blocked():
            try:await gate.wait();return slow
            finally:state["closed"]=True
        async def ready():return fast
        jobs=[EvalJob("case1",blocked),EvalJob(fast.case_id,ready)]
        stream=evaluation_report(jobs);header=await stream.__anext__()
        try:first=await asyncio.wait_for(stream.__anext__(),0.5)
        except asyncio.TimeoutError:raise AssertionError("a completed evaluation case is observable while another case remains pending")
        first_case=ET.fromstring(header+first+"</testsuite>").find("testcase")
        assert first_case.attrib["name"]==fast.case_id and first_case.attrib["classname"]==fast.category, "a completed evaluation case is observable while another case remains pending"
        gate.set();pieces=[header,first]+[piece async for piece in stream];root=ET.fromstring("".join(pieces))
        cases={case.attrib["name"]:case for case in root.findall("testcase")}
        assert list(cases)==[fast.case_id,"case1"] and json.loads(cases[fast.case_id].findtext("system-out"))=={"output":fast.model_output,"reference":fast.reference_output}, "XML report text and case identity remain data rather than structure"
        assert cases[fast.case_id].attrib["time"]=="0.000001" and cases["case1"].find("failure") is not None and state["closed"], "case duration and failed judge evidence remain attached to the completed case"
        assert [child.tag for child in cases[fast.case_id]]==["system-out"], "successful judge cases have no failure error or skipped outcome"
        async def normalized():
            for result in [CompletedCase("missing","factual","output",None,0,None),CompletedCase("error","factual","partial","reference",7,True,"judge<error>&"),CompletedCase("empty_error","factual","partial",None,0,True,"")]:yield result
        from evalpair.junit import encode_junit
        states=ET.fromstring("".join([piece async for piece in encode_junit(normalized())]))
        assert [child.tag for child in states.findall("testcase")[0] if child.tag!="system-out"]==["skipped"] and [case.find("error").attrib["message"] for case in states.findall("testcase")[1:]]==["judge<error>&",""], "missing judge results and runtime errors retain distinct XML outcomes including empty error messages"
        assert ET.fromstring("".join([piece async for piece in evaluation_report([])])).findall("testcase")==[], "an empty evaluation report is a complete parseable XML suite"
        async def conflicted():yield CompletedCase("conflicted","factual","partial",None,0,False,"runtime error")
        conflict=ET.fromstring("".join([piece async for piece in encode_junit(conflicted())])).find("testcase")
        assert [child.tag for child in conflict]==["error","system-out"] and conflict.find("error").attrib["message"]=="runtime error", "runtime errors take precedence over a false judge verdict"
        gate.clear();state["closed"]=False;early=evaluation_report(jobs);await early.__anext__();await early.__anext__();await early.aclose()
        assert state["closed"], "closing the report releases unfinished evaluation jobs"
    asyncio.run(exercise())

@pytest.mark.skip("Part 5")
def test_category_paired_coverage_tree():
    """Keep same-case criterion coverage and original category comparison evidence paths."""
    suite=SuiteSpec("paired-bank",(CategorySpec("safety",(CaseSpec("s1",("correctness",)),CaseSpec("s2",("correctness",)))),CategorySpec("core",(CaseSpec("c1",("correctness","helpfulness")),CaseSpec("c2",("correctness",)))),CategorySpec("pending",(CaseSpec("e1",("safety",)),))))
    baseline=[observation("s1","safety","correctness","1"),observation("c1","core","correctness","0"),observation("c1","core","helpfulness","2"),observation("c2","core","correctness",None)]
    variant=[observation("s2","safety","correctness","2"),observation("c2","core","correctness","4"),observation("c1","core","helpfulness",None),observation("c1","core","correctness","0")]
    negative=Interval(1,-2,-2,-2);positive=Interval(2,2,1,3);comparison=Comparison(Interval(3,1,0.5,2),{}, {"core":positive,"safety":negative},False)
    report=coverage_tree(suite,baseline,variant,comparison);safety,core,pending=report["categories"]
    assert report["counts"]=={"paired":1,"baseline_only":2,"variant_only":2,"neither":1}, "coverage pairs only the same case and criterion rather than equal category totals"
    assert safety["paired_by_criterion"]=={"correctness":0} and [case["criteria"][0]["state"] for case in safety["cases"]]==["baseline_only","variant_only"], "unmatched baseline and variant cases retain their own category evidence paths"
    assert core["paired_by_criterion"]=={"correctness":1,"helpfulness":0} and core["cases"][0]["criteria"][0]=={"criterion":"correctness","state":"paired","path":("categories",1,"cases",0,"criteria",0)}, "each criterion retains its own pair count and declared typed location"
    assert core["cases"][0]["criteria"][1]=={"criterion":"helpfulness","state":"baseline_only","path":("categories",1,"cases",0,"criteria",1)}, "every criterion retains its own declared typed index"
    assert [category["name"] for category in report["categories"]]==["safety","core","pending"] and pending["counts"]["neither"]==1, "every declared category remains present in its input order including wholly unjudged cases"
    assert safety["evidence"] is negative and safety["evidence_path"]==("categories","safety") and core["evidence"] is positive and pending["evidence"] is None, "category evidence keeps its original comparison object and path despite a favorable overall interval"
    assert coverage_tree(SuiteSpec("empty",()),[],[],Comparison(None,{},{},True))=={"name":"empty","counts":{"paired":0,"baseline_only":0,"variant_only":0,"neither":0},"categories":[]}, "an empty declared suite has no fabricated comparison evidence"
    empty_categories=coverage_tree(SuiteSpec("declared-empty",(CategorySpec("vacant",()),)),[],[],Comparison(None,{}, {"vacant":negative},False))["categories"]
    assert len(empty_categories)==1, "empty declared categories retain their zero coverage and original evidence"
    empty_category=empty_categories[0]
    assert empty_category["name"]=="vacant" and empty_category["cases"]==[] and empty_category["paired_by_criterion"]=={} and empty_category["counts"]=={"paired":0,"baseline_only":0,"variant_only":0,"neither":0} and empty_category["evidence"] is negative and empty_category["evidence_path"]==("categories","vacant"), "empty declared categories retain their zero coverage and original evidence"
