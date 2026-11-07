"""Five independent practice stages; remove only the active Part lock."""
import asyncio,csv,io,time
from dataclasses import replace
from fractions import Fraction as F
import pytest
from prefixmeter.contracts import LifecycleProfile,PriceProfile,Request,Observation,Lifetime,Collection,RunHeader,Section
from prefixmeter.traffic import collect_traffic
from prefixmeter.journal import AccountingJournal
from prefixmeter.pricing import price_collection,break_even_reads
from prefixmeter.event_driver import publish_traffic
from prefixmeter.layout import plan_prefix

def raw(i,at,key="stable",profile="a",prefix="1000",suffix=20):
    return dict(request_id=str(i),profile_id=profile,prefix_key=key,prefix_tokens=prefix,suffix_tokens=suffix,timestamp_us=at)
def stress_inputs(n=2500,width=16000):
    shared="system: stable evidence "*(width//24)
    keys=tuple(shared+"/document/"+str(i) for i in range(80))
    rows=tuple(raw(i,i*1000,keys[i%80],prefix="5000",suffix=2) for i in range(n))
    return rows,{"a":LifecycleProfile("a",10000000)},3000000

def consume_stress(result,rows,horizon):
    assert result.run_id=="pressure" and result.report_horizon_us==horizon and len(result.observations)==len(rows) and len(result.lifetimes)==80,"large traffic reports retain every observation and write object"
    for i,(actual,source) in enumerate(zip(result.observations,rows)):
        assert (actual.run_id,actual.request_id,actual.profile_id,actual.prefix_key,actual.kind,actual.prefix_tokens,actual.suffix_tokens,actual.timestamp_us,actual.total_input_tokens)==("pressure",str(i),"a",source["prefix_key"],"WRITE" if i<80 else "READ",5000,2,i*1000,5002),"large traffic reports preserve complete typed request evidence"
        assert actual.object_id==result.lifetimes[i%80].object_id,"each request references its actual scoped write object"
    for i,life in enumerate(result.lifetimes):
        assert (life.run_id,life.profile_id,life.prefix_key,life.prefix_tokens,life.created_us,life.observed_end_us,life.expires_us)==("pressure","a",rows[i]["prefix_key"],5000,i*1000,horizon,i*1000+10000000),"large traffic reports retain complete write intervals"

def billing_fixture():
    observations=(Observation("bill","w0","a","P","WRITE","o0",1000,100,0,1100),Observation("bill","r0","a","P","READ","o0",1000,100,1000000,1100),Observation("bill","w1","a","P","WRITE","o1",1000,100,4000000,1100),Observation("bill","u","b","short","UNCACHED",None,500,20,4500000,520))
    lives=(Lifetime("bill","o0","a","P",1000,0,4000000,4000000),Lifetime("bill","o1","a","P",1000,4000000,5000000,8000000))
    return Collection("bill",5000000,observations,lives),{"a":PriceProfile("a","1.00","1.25","0.10","3.60"),"b":PriceProfile("b","2.0","2.5","0.2","0")}

@pytest.mark.skip("Part 1")
def test_typed_traffic_and_write_lifetimes():
    """Typed observations, complete write lifetimes and responsive exact-prefix collection."""
    profiles={"a":LifecycleProfile("a",5000000),"b":LifecycleProfile("b",5000000,2000)}
    rows=(raw(0,0),raw(1,4000000),raw(2,5000000),raw(3,6000000,profile="b"))
    result=collect_traffic(rows,profiles,9000000,"lifetime")
    assert tuple(x.total_input_tokens for x in result.observations)==(1020,)*4,"supplied numeric token spellings become typed input usage"
    assert tuple((x.created_us,x.observed_end_us) for x in result.lifetimes)==((0,5000000),(5000000,9000000)),"all real writes retain their own observed lifetimes after prefix rewrites"
    assert tuple(x.kind for x in result.observations)==("WRITE","READ","WRITE","UNCACHED"),"declared fixed write expiry and minimum-token policy determine observed roles"
    assert result.observations[0].object_id==result.observations[1].object_id!=result.observations[2].object_id and result.observations[3].object_id is None,"write object ownership survives hits and replacements"
    scoped=collect_traffic((raw(0,0),raw(1,0,profile="c")),{"a":profiles["a"],"c":LifecycleProfile("c",5000000)},1,"scoped")
    assert len(scoped.lifetimes)==2 and all(x.kind=="WRITE" for x in scoped.observations),"equal exact prefixes in different profiles are independent objects"
    with pytest.raises(ValueError,match="chronology"):collect_traffic((raw(0,2),raw(1,1)),profiles,3,"backward")
    rows,profiles,horizon=stress_inputs();start=time.perf_counter();large=collect_traffic(rows,profiles,horizon,"pressure");consume_stress(large,rows,horizon);elapsed=time.perf_counter()-start
    assert elapsed<0.1,"large exact-prefix traffic collections should stay responsive"

@pytest.mark.skip("Part 2")
def test_typed_accounting_journal(tmp_path):
    """Append complete supplied records, then recover independent run/profile evidence."""
    collection,prices=billing_fixture();path=tmp_path/"traffic.jsonl";journal=AccountingJournal(path)
    special=PriceProfile("precise","1.00000000000000000001","1.2500","0.1000","0.0000000000000000000003")
    other=Observation("other","w0","precise","line\u2028\u0085,\n","WRITE","other-object",5,7,8,12)
    other_life=Lifetime("other","other-object","precise",other.prefix_key,5,8,9,10)
    records=(prices["a"],special,RunHeader("bill",5000000,("a","b")),prices["b"],RunHeader("other",9,("precise",)),*collection.observations,*collection.lifetimes,other,other_life)
    for record in records:journal.append(record)
    replay=AccountingJournal(path).replay()
    assert replay.records==records,"journal reopen preserves every typed record in append order"
    assert replay.runs["bill"].observations==collection.observations and replay.runs["bill"].lifetimes==collection.lifetimes,"run views retain reads uncached requests and every expired write object"
    assert replay.runs["other"].observations==(other,) and replay.runs["other"].lifetimes==(other_life,),"run identity separates repeated request names and exact prefix payloads"
    assert replay.runs["bill"].prices==prices and replay.runs["other"].prices=={"precise":special},"each run binds only its declared immutable price profiles"
    assert replay.prices["precise"]==special,"the supplied complete record codec retains original price evidence"
    journal.append(replace(prices["a"],read_text="0.2"))
    with pytest.raises(ValueError,match="conflicting price"):journal.replay()
    unknown=AccountingJournal(tmp_path/"unknown.jsonl");unknown.append(other)
    with pytest.raises(ValueError,match="undeclared run"):unknown.replay()
    assert AccountingJournal(tmp_path/"absent").replay().records==(),"an absent journal represents no observations"

    duplicate=AccountingJournal(tmp_path/"duplicate-object.jsonl")
    duplicate_life=replace(collection.lifetimes[0],run_id="duplicate")
    for record in (prices["a"],RunHeader("duplicate",5000000,("a",)),duplicate_life,duplicate_life):duplicate.append(record)
    with pytest.raises(ValueError,match="duplicate storage object"):duplicate.replay()
    association=AccountingJournal(tmp_path/"association.jsonl")
    foreign=replace(collection.observations[0],run_id="association",profile_id="b")
    for record in (prices["a"],prices["b"],RunHeader("association",5000000,("a",)),foreign):association.append(record)
    with pytest.raises(ValueError,match="run profile association"):association.replay()

@pytest.mark.skip("Part 3")
def test_exact_role_storage_and_strict_inverse():
    """Exact full-request rates, every observed object-hour and minimal strict savings."""
    collection,prices=billing_fixture();report=price_collection(collection,prices)
    assert report.input_cost==F(197,50),"prefix role rates and all changing suffix tokens contribute to input charges"
    assert report.storage_cost==F(1,200),"all real object lifetimes contribute observed microsecond token-hours"
    assert report.total_cost==F(789,200) and report.baseline==F(217,50),"total and uncached baseline include all profiles and suffixes"
    assert report.savings==(report.baseline-report.total_cost)/report.baseline,"savings compares complete observed charges with their full baseline"
    assert report.per_profile["a"]=={"input_cost":F(29,10),"storage_cost":F(1,200),"baseline":F(33,10),"total_cost":F(581,200)},"profile subtotals retain independent rate roles and storage charges"
    tiny=Collection("tiny",1,(),(Lifetime("tiny","x","a","p",3,0,1,2),))
    assert price_collection(tiny,prices).storage_cost==F(3,1000000000000),"short observed storage intervals retain exact unit precision"
    assert break_even_reads(F(1),F(2),F(1,2),F(0))==3,"break even requires strict savings beyond an equality boundary"
    assert break_even_reads(F(1),F(1,2),F(2),F(0))==0,"an already cheaper write window needs no further read"
    assert break_even_reads(F(1),F(2),F(1),F(0)) is None and break_even_reads(F(1),F(2),F(3),F(1)) is None,"unfavorable read economics cannot promise eventual savings"
    empty=price_collection(Collection("empty",0,(),()),prices)
    assert (empty.total_cost,empty.baseline,empty.savings)==(0,0,0),"zero-use reports have explicit zero economics"

    assert break_even_reads(F(1),F(1),F(0),F(1))==2,"storage overhead participates in the minimal strict savings inverse"
    assert break_even_reads(F(1),F(2**60),F(0),F(0))==2**60,"large exact money preserves the last integer below strict savings"

@pytest.mark.skip("Part 4")
def test_csv_real_clock_accounting():
    """Incremental actual-time role accounting with independent cumulative input/storage totals."""
    class Feed:
        def __init__(self,rows):self.rows=iter(rows);self.pulled=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            try:value=next(self.rows)
            except StopIteration:raise StopAsyncIteration
            self.pulled+=1;return value
        async def aclose(self):self.closed=True
    def parse(header,line):return next(csv.DictReader(io.StringIO(header+line)))
    async def check():
        profiles={"a":LifecycleProfile("a",4000000),"b":LifecycleProfile("b",4000000,2000)}
        prices={"a":PriceProfile("a","1","1.25","0.1","3.6"),"b":PriceProfile("b","2","2.5","0.2","0")}
        rows=(raw(0,0,"q,\n\"中文"),raw(1,1000000,"q,\n\"中文"),raw(2,4000000,"q,\n\"中文"),raw(3,4500000,"short","b",prefix="500"))
        feed=Feed(rows);stream=publish_traffic(feed,profiles,prices,5000000,"events");header=await stream.__anext__()
        first=parse(header,await stream.__anext__())
        assert feed.pulled==1 and first["request_id"]=="0" and first["prefix_key"]==rows[0]["prefix_key"],"a completed accounting event publishes its complete current identity and CSV payload"
        rest=[parse(header,chunk) async for chunk in stream];data=[first]+rest
        assert tuple((x["timestamp_us"],x["kind"]) for x in data)==(("0","WRITE"),("1000000","READ"),("4000000","WRITE"),("4500000","UNCACHED"),("","TOTAL")),"event timestamps and cache roles describe actual observed traffic"
        assert tuple(F(x["storage_cost"]) for x in data)==(F(1,250),F(1,250),F(1,200),F(1,200),F(1,200)),"read events retain cumulative storage without creating another write lifetime"
        assert (F(data[-1]["input_cost"]),F(data[-1]["total_cost"]),data[-1]["requests"],data[-1]["writes"],data[-1]["reads"],data[-1]["uncached"])==(F(37,10),F(741,200),"4","2","1","1"),"the final accounting row retains all event charges and role counts"
        assert feed.closed,"the given accounting driver closes its exhausted source"
        early=Feed(rows);stream=publish_traffic(early,profiles,prices,5000000,"early");await stream.__anext__();await stream.aclose()
        assert early.pulled==0 and early.closed,"closing after the CSV header closes the unconsumed source"
        empty=Feed(());chunks=[x async for x in publish_traffic(empty,profiles,prices,0,"empty")];end=parse(chunks[0],chunks[1])
        assert end["kind"]=="TOTAL" and end["requests"]=="0" and F(end["total_cost"])==0,"empty completed accounting streams include explicit final totals"
    asyncio.run(check())

@pytest.mark.skip("Part 5")
def test_nested_exact_prefix_breakpoint():
    """Ordered nested prompt sections, volatile ancestors and complete shared leaf boundaries."""
    root=Section("prompt",True,children=(Section("tools",True,("toolB","toolA")),Section("static",True,children=(Section("system",True,("S",)),Section("examples",True,("E1","E2")))),Section("turn",False,("Q",)),Section("footer",True,("tail",))))
    paths=(("prompt","tools"),("prompt","static","system"),("prompt","static","examples"),("prompt","turn"),("prompt","footer"))
    variants=({paths[0]:("toolB","toolA"),paths[1]:("S",),paths[2]:("E1","E2"),paths[3]:("Q1",),paths[4]:("tail",)},{paths[0]:("toolB","toolA"),paths[1]:("S",),paths[2]:("E1","E2"),paths[3]:("Q2",),paths[4]:("tail",)})
    result=plan_prefix(root,variants)
    assert result.leaf_paths==paths and result.original_variants==(("toolB","toolA","S","E1","E2","Q1","tail"),("toolB","toolA","S","E1","E2","Q2","tail")),"nested layout preserves every original section and token in declared order"
    assert (result.cacheable_tokens,result.breakpoint_path,result.first_volatile_path,result.shared_token_count)==(("toolB","toolA","S","E1","E2"),paths[2],paths[3],5),"the selected breakpoint ends at the latest common stable complete section"
    partial=({**variants[0],paths[2]:("E1","different")},variants[1]);cut=plan_prefix(root,partial)
    assert cut.cacheable_tokens==("toolB","toolA","S") and cut.shared_token_count==4 and cut.breakpoint_path==paths[1],"a difference inside one section cannot create a partial-section breakpoint"
    unstable=Section("root",False,children=(Section("child",True,("fixed",)),))
    blocked=plan_prefix(unstable,())
    assert blocked.cacheable_tokens==() and blocked.first_volatile_path==("root","child"),"volatile status inherited from an ancestor forbids a descendant cache boundary"
    unicode=Section("root",True,children=(Section("same",True,("x",)),Section("unicode",True,("é",))))
    variants=({("root","same"):("x",),("root","unicode"):("é",)},{("root","same"):("x",),("root","unicode"):("e\u0301",)})
    assert plan_prefix(unicode,variants).cacheable_tokens==("x",),"prefix comparison preserves exact token spellings without Unicode normalization"
    empty=plan_prefix(Section("empty",True),())
    assert empty.cacheable_tokens==() and empty.breakpoint_path is None and empty.original_variants==((),),"an empty layout has no positive cache breakpoint"

    positive=Section("positive",True,children=(Section("content",True,("A",)),Section("empty",True)))
    positive_plan=plan_prefix(positive,())
    assert positive_plan.breakpoint_path==("positive","content"),"only a positive-length leaf can supply a cache breakpoint"
    assert positive_plan.leaf_paths==(("positive","content"),("positive","empty")),"empty sections remain part of the complete original layout"
    leading=Section("leading",True,children=(Section("empty",True),Section("content",True,("A",))))
    leading_plan=plan_prefix(leading,())
    assert leading_plan.cacheable_tokens==("A",) and leading_plan.breakpoint_path==("leading","content"),"an empty stable section does not block a later legal positive leaf"
    multi=Section("multi",True,children=(Section("common",True,("a",)),Section("detail",True,("b",))))
    first={("multi","common"):("a",),("multi","detail"):("b",)}
    third={**first,("multi","common"):("x",)}
    multi_plan=plan_prefix(multi,(first,dict(first),third))
    assert multi_plan.shared_token_count==0 and multi_plan.cacheable_tokens==() and multi_plan.breakpoint_path is None,"every supplied observation constrains the exact shared prefix"
    sized=Section("sized",True,children=(Section("first",True,("template",)),Section("last",True,("end",))))
    rendered={("sized","first"):("long","prefix"),("sized","last"):("tail",)}
    sized_plan=plan_prefix(sized,(rendered,dict(rendered)))
    assert sized_plan.cacheable_tokens==("long","prefix","tail") and sized_plan.breakpoint_path==("sized","last"),"legal leaf endpoints use the actual rendered variant token lengths"
