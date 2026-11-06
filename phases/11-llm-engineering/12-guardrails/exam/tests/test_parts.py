import asyncio,hashlib,json,time
from dataclasses import replace
from pathlib import Path
import pytest
from piispan.contracts import Recognizer,Span,AuditSpan,Transcript,StoredTranscript,GuardrailResult as Check,GuardrailReport as Report,Trace,Message,BLOCKED_INPUT,BLOCKED_OUTPUT
from piispan.legacy import GuardService,collect_disjoint,apply_spans
from piispan.fingerprint import pii_fingerprint
from piispan.store import TranscriptStore
from piispan.overlap import resolve_overlaps,scrub_overlaps
from piispan.pipeline import Sandwich,publish
from piispan.audit import audit_sandwich
PHONE=Recognizer("phone",r"\b(\d{3})-(\d{3})-(\d{4})\b",3,"0.9500000000000000000001","[PHONE]")
EMAIL=Recognizer("email",r"\b([a-z]{1,8})@([a-z]{1,8})\.org\b",2,"0.9500","[E]")
def fingerprint(value,salt="case"):
    return hashlib.sha256(salt.encode()+b"\0"+value.encode()).hexdigest()[:12]
def span(text,start,end,priority=1,kind="entity",placeholder="[X]",confidence="0.95"):
    return Span(start,end,text[start:end],kind,priority,confidence,placeholder)
@pytest.mark.skip("Part 1")
def test_original_interval_scrub():
    """Repair full-match projection, original offsets, scrub policy and large output handling."""
    one=GuardService((PHONE,),"case").inspect("Call 415-555-0101.")
    assert one.transcript.spans==(AuditSpan(5,17,"phone",fingerprint("415-555-0101"),PHONE.confidence_text),),"PII fingerprints cover each complete matched value"
    text="你好😀 alpha@bank.org next 415-555-0101 end"
    service=GuardService((EMAIL,PHONE),"case");result=service.inspect(text)
    expected=((text.index("alpha@bank.org"),text.index("alpha@bank.org")+14),(text.index("415-555-0101"),text.index("415-555-0101")+12))
    assert tuple((s.start,s.end) for s in result.transcript.spans)==expected,"all audit intervals refer to the original Unicode text"
    assert not result.blocked and result.delivered=="你好😀 [E] next [PHONE] end","successful PII scrubbing delivers the sanitized response"
    assert result.transcript.original==text and result.transcript.spans[1].fingerprint==fingerprint("415-555-0101"),"safe audit keeps original evidence without changing the input"
    hard=service.inspect(text,(Check(False,"toxicity","toy unsafe", "0.99"),))
    assert hard.blocked and hard.delivered==BLOCKED_OUTPUT,"a true hard output failure still blocks delivery"
    empty=service.inspect("")
    assert empty.delivered=="" and not empty.blocked and empty.transcript.spans==(),"a clean empty response remains a valid response"
    repeated=GuardService((PHONE,),"case").inspect("415-555-0101 / 415-555-0101")
    assert len(repeated.transcript.spans)==2 and repeated.delivered=="[PHONE] / [PHONE]","repeated PII values retain separate source occurrences"
    assert apply_spans("before after",())=="before after","text outside detected intervals is preserved"
    pieces=[f"record{i}: {200+i:03}-555-{i:04} "+"public_context_"*40+"\n" for i in range(500)]
    large=''.join(pieces)
    expected_large=''.join(f"record{i}: [PHONE] "+"public_context_"*40+"\n" for i in range(500))
    started=time.perf_counter()
    stress=GuardService((PHONE,),"pressure").inspect(large)
    elapsed=time.perf_counter()-started
    assert not stress.blocked and stress.delivered==expected_large and len(stress.transcript.spans)==500,"large scrub requests retain every redaction and public character"
    assert stress.transcript.spans[0].fingerprint==fingerprint("200-555-0000","pressure") and stress.transcript.spans[-1].fingerprint==fingerprint("699-555-0499","pressure"),"large scrub requests retain complete original fingerprint evidence"
    assert elapsed<0.06,"large transcript scrubbing should stay responsive"
@pytest.mark.skip("Part 2")
def test_safe_transcript_store(tmp_path):
    """Content-address only sanitized bytes and preserve each transcript's independent audit."""
    root=tmp_path/"safe";store=TranscriptStore(root);suffix="\r\n你好😀\u2028tail"
    first=Transcript("415-555-0101"+suffix,"[PHONE]"+suffix,(AuditSpan(0,12,"phone",fingerprint("415-555-0101"),"0.9500000000000000000001"),))
    second=Transcript("212-555-0199"+suffix,"[PHONE]"+suffix,(AuditSpan(0,12,"phone",fingerprint("212-555-0199"),"0.9500"),))
    store.save("first",first);store.save("second",second);store=TranscriptStore(root)
    assert store.load("first")==StoredTranscript(first.redacted,first.spans),"a reopened transcript retains exact redacted bytes and original audit fields"
    assert store.load("second")==StoredTranscript(second.redacted,second.spans),"equal redacted payloads retain independent transcript audit identities"
    blobs=list((root/"blobs").iterdir())
    assert len(blobs)==1 and blobs[0].read_bytes()==first.redacted.encode("utf-8"),"equal sanitized content shares one exact payload blob"
    files=[p.read_bytes() for p in root.rglob("*") if p.is_file()]
    assert all(b"415-555-0101" not in data and b"212-555-0199" not in data for data in files),"persisted transcript artifacts contain no original PII values"
    assert all("original" not in json.loads((root/(key+".json")).read_bytes()) for key in ("first","second")),"safe audit manifests contain no raw original transcript field"
    newer=replace(second,spans=(replace(second.spans[0],confidence_text="0.9500000000000000000002"),))
    store.save("second",newer)
    assert store.load("first").spans==first.spans and store.load("second").spans==newer.spans,"a transcript audit update cannot change another key's evidence"
    third=Transcript("runtime original excluded","public third payload\r\n😀",())
    store.save("third",third)
    assert store.load("first")==StoredTranscript(first.redacted,first.spans),"multiple sanitized blobs retain each earlier manifest owner"
    assert store.load("third")==StoredTranscript(third.redacted,()),"each manifest selects its own complete sanitized payload"
    payload=root/"blobs"/hashlib.sha256(third.redacted.encode("utf-8")).hexdigest()
    payload.write_bytes(b"altered sanitized payload")
    with pytest.raises(ValueError,match="payload digest"):store.load("third")
    files_before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
    invalid=replace(third,redacted="unpublished invalid audit body",spans=(AuditSpan(0,0,"phone",fingerprint("415-555-0101"),"0.9"),))
    with pytest.raises(ValueError,match="audit offsets"):store.save("invalid",invalid)
    assert {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}==files_before,"invalid audit leaves all persisted transcript artifacts unchanged"
@pytest.mark.skip("Part 3")
def test_overlap_arbitration():
    """Resolve priority/coverage overlaps before rendering any original interval."""
    text="abcdefghijklmno"
    outer=span(text,0,10,1,"outer");inner=span(text,2,5,4,"inner");bridge=span(text,4,9,3,"bridge");later=span(text,6,9,2,"later");tail=span(text,10,12,1,"tail")
    original=[tail,outer,bridge,later,inner];before=list(original)
    chosen=resolve_overlaps(text,original)
    assert chosen==(inner,later,tail),"higher-priority accepted intervals determine which overlaps remain eligible"
    assert original==before,"overlap arbitration preserves its input candidates"
    adjacent=[span("abcd",0,2,1,"left"),span("abcd",2,4,1,"right")]
    assert resolve_overlaps("abcd",adjacent)==tuple(adjacent),"adjacent half-open intervals remain separate entities"
    wide=span(text,0,4,2,"wide");short=span(text,0,2,2,"short")
    assert resolve_overlaps(text,[short,wide])==(wide,),"equal-priority overlap favors the greater covered interval"
    lower=span(text,0,3,2,"z");higher=span(text,1,4,2,"a")
    assert resolve_overlaps(text,[higher,lower])==(lower,),"equal-priority equal-length overlap favors the earlier source interval"
    a=span(text,0,3,2,"a");z=span(text,0,3,2,"z")
    assert resolve_overlaps(text,[z,a])==(a,),"identical intervals use the declared kind ordering"
    duplicate=replace(a,confidence_text="0.99")
    assert resolve_overlaps(text,[duplicate,a])==(duplicate,),"fully tied candidates retain original candidate order"
    repeated="xx xx";values=[span(repeated,0,2,1,"pii"),span(repeated,3,5,1,"pii")]
    result=scrub_overlaps(repeated,values,"case")
    assert result.redacted=="[X] [X]" and tuple((s.start,s.end) for s in result.spans)==((0,2),(3,5)),"equal PII values retain every independent selected occurrence"
    assert result.spans[0].fingerprint==result.spans[1].fingerprint==fingerprint("xx"),"selected interval fingerprints retain their complete original values"
    with pytest.raises(ValueError,match="span value"):resolve_overlaps(text,[replace(inner,value="wrong")])
    assert resolve_overlaps("",[])==(),"empty span candidates produce an empty selection"
    ordered=[span(text,0,2,1,"left"),span(text,10,12,9,"right")]
    assert resolve_overlaps(text,ordered)==tuple(ordered),"selected intervals retain original-text order independently of priority"
@pytest.mark.skip("Part 4")
def test_safe_message_publication():
    """Publish sanitized completed-message outcomes and safe two-stage audit records."""
    calls=[];pulled=[];closed=[]
    def inputs(prompt):
        if prompt=="blocked":return (Check(False,"injection","private input", "0.99",3),Check(False,"pii_detection","private PII", "0.98",4))
        return (Check(True,"length_check","private input notes", "0.0",1),)
    def outputs(prompt,raw):return (Check(prompt!="toxic","toxicity","private output "+raw,"0.99" if prompt=="toxic" else "0.01",5),)
    def replay(prompt):
        calls.append(prompt)
        if prompt=="blocked":raise AssertionError("blocked input reached replay")
        return {"contact":"Call 415-555-0101.","toxic":"toy unsafe response","empty":""}[prompt]
    sandwich=Sandwich((PHONE,),"case",inputs,outputs)
    async def source():
        try:
            for name in ("contact","blocked","toxic","empty"):
                pulled.append(name);yield Message("request-"+name,name,replay)
        finally:closed.append(True)
    async def run():
        stream=publish(source(),sandwich).__aiter__();line=await stream.__anext__();first=json.loads(line)
        assert pulled==["contact"] and calls==["contact"],"a complete guarded message is published before later input is requested"
        assert line.endswith("\n") and line.count("\n")==1 and first["request_id"]=="request-contact","the supplied driver publishes one complete current-owner JSON line"
        assert first["outcome"]=="scrubbed" and first["response"]=="Call [PHONE].","published scrubbed messages contain the delivered sanitized response"
        audit=first["audit"]
        assert [x["category"] for x in audit["input_results"]]==["length_check"] and [x["category"] for x in audit["output_results"]]==["toxicity","pii_scrubbing"],"safe audit preserves the correct input and output result stages"
        assert all(set(x)=={"category","passed","confidence_text","latency_us"} for stage in ("input_results","output_results") for x in audit[stage]) and "private" not in line and "415-555-0101" not in line,"public audit fields exclude raw check details and sensitive text"
        assert audit["pii_spans"]==[{"start":5,"end":17,"kind":"phone","fingerprint":fingerprint("415-555-0101"),"confidence_text":PHONE.confidence_text}],"published PII audit retains original intervals and exact confidence text"
        assert audit["input_results"]==[{"category":"length_check","passed":True,"confidence_text":"0.0","latency_us":1}] and audit["output_results"]==[{"category":"toxicity","passed":True,"confidence_text":"0.01","latency_us":5},{"category":"pii_scrubbing","passed":False,"confidence_text":PHONE.confidence_text,"latency_us":0}],"safe check projection retains exact values in each execution stage"
        blocked=json.loads(await stream.__anext__())
        assert blocked["outcome"]=="blocked_input" and blocked["response"]==BLOCKED_INPUT and blocked["audit"]["output_results"]==[] and calls==["contact"],"input blocks publish typed safe outcomes without downstream execution"
        toxic=json.loads(await stream.__anext__())
        assert toxic["outcome"]=="blocked_output" and toxic["response"]==BLOCKED_OUTPUT and "toy unsafe response" not in json.dumps(toxic),"hard output failures publish the guarded refusal and safe evidence"
        empty=json.loads(await stream.__anext__())
        assert empty["outcome"]=="approved" and empty["response"]=="" and empty["request_id"]=="request-empty","approved empty responses retain their own outcome and identity"
        with pytest.raises(StopAsyncIteration):await stream.__anext__()
        assert closed==[True] and calls==["contact","toxic","empty"],"normal completion closes the local replay source"
        pull=[]
        async def short():
            try:
                for name in ("contact","toxic"):
                    pull.append(name);yield Message(name,name,replay)
            finally:early.append("closed")
        early=[];stream=publish(short(),sandwich);await stream.__anext__();await stream.aclose()
        assert pull==["contact"] and early==["closed"],"early close stops pulling and closes the supplied source"
        async def unicode_source():
            yield Message("unicode","contact",lambda _:"😀 415-555-0101")
        unicode_stream=publish(unicode_source(),sandwich)
        record=json.loads(await unicode_stream.__anext__())
        assert record["response"]=="😀 [PHONE]" and record["audit"]["pii_spans"]==[{"start":2,"end":14,"kind":"phone","fingerprint":fingerprint("415-555-0101"),"confidence_text":PHONE.confidence_text}],"published Unicode PII audit retains original codepoint intervals"
        await unicode_stream.aclose()
    asyncio.run(run())
@pytest.mark.skip("Part 5")
def test_report_stage_evidence():
    """Validate source report nesting and count blocked requests rather than failed checks."""
    passed=Check(True,"length","safe","0.0",1);injection=Check(False,"injection","safe hash","0.99",2);pii_in=Check(False,"pii_detection","safe hash","0.98",3)
    toxicity=Check(False,"toxicity","safe","0.99",4);relevance=Check(False,"relevance","safe","0.8",5);scrub=Check(False,"pii_scrubbing","safe hashes","0.95",6);clean=replace(scrub,passed=True,confidence_text="0")
    input_block=Trace(Report((injection,pii_in),(),True,"Input blocked: injection",7),False,False,BLOCKED_INPUT,None,(),"blocked_input")
    output_block=Trace(Report((passed,),(toxicity,relevance,scrub),True,"Output blocked: toxicity",20),True,False,BLOCKED_OUTPUT,"private",(),"blocked_output")
    sanitized=Trace(Report((passed,),(scrub,),False,"",9),True,True,"[P]","private",(),"scrubbed")
    plain=Trace(Report((passed,),(clean,),False,"",3),True,False,"public","public",(),"approved")
    result=audit_sandwich(iter((input_block,output_block,sanitized,plain)))
    assert result["totals"]=={"requests":4,"passed":2,"blocked_input":1,"blocked_output":1,"pii_scrubbed":1},"sandwich totals count each request once and retain safe scrub events"
    assert result["block_categories"]=={"injection":1,"toxicity":1},"block categories retain each request's first hard failure"
    assert result["evidence"][0]["failed_paths"]==((0,"input_results",0,"injection"),(0,"input_results",1,"pii_detection")),"input evidence retains all failed detector paths under the blocked request"
    assert result["evidence"][1]["failed_paths"]==((1,"output_results",0,"toxicity"),(1,"output_results",1,"relevance"),(1,"output_results",2,"pii_scrubbing")),"output evidence retains all detector failures without extra request counts"
    assert result["evidence"][2]["stage"]=="passed" and result["evidence"][2]["report"] is sanitized.report,"safe scrub evidence preserves the original permitted output report"
    bad=replace(input_block,model_called=True)
    with pytest.raises(ValueError,match="input-block evidence"):audit_sandwich([bad])
    bad=replace(input_block,report=replace(input_block.report,output_results=(clean,)))
    with pytest.raises(ValueError,match="input-block evidence"):audit_sandwich([bad])
    with pytest.raises(ValueError,match="passed/scrub evidence"):audit_sandwich([replace(plain,pii_scrubbed=True)])
    with pytest.raises(ValueError,match="output-block evidence"):audit_sandwich([replace(output_block,report=replace(output_block.report,blocked=False))])
    with pytest.raises(ValueError,match="block reason evidence"):audit_sandwich([replace(input_block,report=replace(input_block.report,block_reason="Input blocked: pii_detection"))])
    assert audit_sandwich([])=={"totals":{"requests":0,"passed":0,"blocked_input":0,"blocked_output":0,"pii_scrubbed":0},"block_categories":{},"evidence":[]},"empty monitoring input retains explicit zero totals and no evidence paths"
    with pytest.raises(ValueError,match="output-stage evidence"):audit_sandwich([replace(plain,model_called=False)])
    bad=replace(output_block,report=replace(output_block.report,output_results=(toxicity,relevance)))
    with pytest.raises(ValueError,match="output-stage evidence"):audit_sandwich([bad])
