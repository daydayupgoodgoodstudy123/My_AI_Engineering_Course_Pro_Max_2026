import asyncio
import csv
import io
import math
import time

import pytest
from rerankdesk.models import Source,ScoredHit
from rerankdesk.catalog_builder import build_catalog
from rerankdesk.search import SearchDesk
from rerankdesk.store import CatalogStore
from rerankdesk.scorer import SourceLexicalScorer
from rerankdesk.stream import stream_batches
from rerankdesk.context import expand_parent_context
from rerankdesk.keyword import KeywordIndex,keyword_candidate_source
from rerankdesk.hyde import LocalHyDERetriever,hyde_generate_hypothesis

@pytest.mark.skip("Part 1")
def test_filtered_candidate_batch():
    """Repair source HyDE roles, metadata prefilter and rerank pool orchestration."""
    catalog=build_catalog([Source("z","Z","high initial","blocked",1),Source("a","A","allowed first","allowed",2),Source("b","B","allowed best","allowed",3)],parent_words=10,child_words=10)
    ids=[row.key for row in catalog.children]
    scores={ids[0]:1.0,ids[1]:2.0,ids[2]:9.0}
    def scorer(query,key,text,initial):return scores[key]+initial
    desk=SearchDesk()
    question="  How is café refund handled?  "
    other_question="What is security evidence?"
    hypothesis=hyde_generate_hypothesis(question)
    other_hypothesis=hyde_generate_hypothesis(other_question)
    retrievals={hypothesis:[(ids[2],0.1),(ids[1],0.2)],other_hypothesis:[(ids[0],0.9),(ids[1],0.25),(ids[2],0.05)]}
    retrieved=[]
    def replay(hypothesis_text):
        retrieved.append(hypothesis_text)
        return retrievals[hypothesis_text]
    retriever=LocalHyDERetriever(replay)
    pair_calls=[]
    def hyde_scorer(query,key,text,initial):
        pair_calls.append((query,key,text,initial))
        return scores[key]+initial
    transformed=desk.query_hyde(question,retriever,catalog,{},1,1,hyde_scorer)
    identity=desk.query("test",[(ids[2],0.1)],catalog,{},1,1,scorer)
    assert len(identity)==1 and identity[0].child_id==ids[2] and identity[0].score==9.1, "reranking consumes original candidate ids, text and supplied scores"
    filtered=desk.query("test",[(ids[0],0.9),(ids[1],0.2),(ids[2],0.1)],catalog,{"category":"allowed"},1,1,scorer)
    assert [row.child_id for row in filtered]==[ids[1]] and filtered[0].initial_rank==2, "metadata admission precedes the retrieval-pool boundary and retains original rank"
    pooled=desk.query("test",[(ids[1],0.9),(ids[2],0.1)],catalog,{},2,1,scorer)
    assert [row.child_id for row in pooled]==[ids[2]] and pooled[0].initial_rank==2, "the complete admitted retrieval pool competes for the final reranked result"
    tied=desk.query("tie",[(ids[2],0.1),(ids[1],0.2)],catalog,{},2,9,lambda *args:0.0)
    assert [row.child_id for row in tied]==[ids[2],ids[1]], "equal supplied relevance retains original candidate order"
    assert desk.query("zero",[(ids[1],0.2)],catalog,{},0,1,scorer)==[] and desk.query("zero",[(ids[1],0.2)],catalog,{},1,0,scorer)==[], "explicit empty pool or final result remains empty"
    assert desk.query("none",[],catalog,{},5,5,scorer)==[], "an absent candidate list does not fabricate a result"
    wide=build_catalog([Source("wide","Batch"," ".join("word"+str(i) for i in range(1600)),"allowed",11)],parent_words=40,child_words=1)
    candidates=[(row.key,(i%17)/1000) for i,row in enumerate(wide.children)]
    supplied={row.key:float((i*37)%103) for i,row in enumerate(wide.children)}
    def pair_score(query,key,text,initial):return supplied[key]+initial
    start=time.perf_counter()
    result=desk.query("local query",candidates,wide,{},1600,7,pair_score)
    elapsed=time.perf_counter()-start
    assert elapsed < 0.05, "large candidate rerank batches should stay responsive"
    expected=sorted(candidates,key=lambda row:-(supplied[row[0]]+row[1]))[:7]
    assert [row.child_id for row in result]==[row[0] for row in expected] and all(row.score==supplied[row.child_id]+row.initial_score for row in result), "responsive reranking preserves complete-pool relevance and exact final scores"
    assert result[0].initial_rank>7 and len(candidates)==1600, "a strong late candidate remains eligible without modifying the original retrieval list"

    # The keyword source and its real initial scores are part of this request.
    keyword=KeywordIndex()
    keyword.index(["s","l","e"],["needle","needle filler filler filler",""])
    rows=keyword_candidate_source("needle",keyword)
    expected_short=math.log(1.6)*2.2/(1+1.2*(0.25+0.75/(5/3)))
    assert [key for key,score in rows]==["s","l","e"] and math.isclose(rows[0][1],expected_short,rel_tol=0,abs_tol=1e-14), "keyword scores use this fitted corpus's length distribution including empty documents"
    changed=keyword_candidate_source("filler",keyword)
    assert changed[0][0]=="l" and changed[0][1]>0 and [score for key,score in changed[1:]]==[0.0,0.0], "a changed question receives fresh keyword scores rather than a previous query's ranking"
    other=KeywordIndex();other.index(["u","v"],["needle filler needle filler needle filler","needle"])
    separate=keyword_candidate_source("needle",other)
    expected_separate=math.log(1.2)*2.2/(1+1.2*(0.25+0.75/3.5))
    assert separate[0][0]=="v" and math.isclose(separate[0][1],expected_separate,rel_tol=0,abs_tol=1e-14) and keyword_candidate_source("needle",keyword)==rows and keyword.avg_dl==5/3 and other.avg_dl==3.5, "independent fitted indexes keep their own corpus statistics and keyword results"
    generation=keyword.generation
    keyword.index(["x","y"],["needle filler filler filler filler","needle"])
    refreshed=keyword_candidate_source("needle",keyword)
    expected_refreshed=math.log(1.2)*2.2/(1+1.2*(0.25+0.75/3))
    assert keyword.generation==generation+1 and refreshed[0][0]=="y" and math.isclose(refreshed[0][1],expected_refreshed,rel_tol=0,abs_tol=1e-14), "replacement indexing refreshes the length statistic consumed by subsequent scoring"
    no_words=KeywordIndex();no_words.index(["e1","e2"],["",""])
    assert no_words.avg_dl==0 and keyword_candidate_source("needle",no_words)==[("e1",0.0),("e2",0.0)] and keyword_candidate_source("needle",KeywordIndex())==[], "all-empty and absent corpora retain their declared zero-score and empty-result behavior"
    texts=["needle "+"filler "*(i%5) for i in range(26000)]
    keyword_catalog=build_catalog([Source(str(i),"Document "+str(i),text,"test",i) for i,text in enumerate(texts)],10,10)
    fitted=KeywordIndex();fitted.index([row.key for row in keyword_catalog.children],texts)
    pair_weights={row.key:(i%13)/10000 for i,row in enumerate(keyword_catalog.children)}
    def source_pair_score(query,key,text,initial):return initial+pair_weights[key]
    start=time.perf_counter()
    generated=keyword_candidate_source("needle",fitted)
    keyword_result=desk.query("needle",generated,keyword_catalog,{},64,7,source_pair_score)
    elapsed=time.perf_counter()-start
    assert elapsed < 0.11, "keyword candidate requests over a fitted corpus should stay responsive"
    expected=sorted(generated[:64],key=lambda row:-(row[1]+pair_weights[row[0]]))[:7]
    assert len(generated)==26000 and {key for key,score in generated}==set(fitted.ids) and [row.child_id for row in keyword_result]==[row[0] for row in expected] and all(row.score==row.initial_score+pair_weights[row.child_id] for row in keyword_result), "responsive keyword generation preserves every candidate and the final consumed rerank result"
    expected_first=math.log(1+0.5/26000.5)*2.2/1.6
    assert math.isclose(generated[0][1],expected_first,rel_tol=0,abs_tol=1e-15) and len({score for key,score in generated})==5 and generated[0][0]==keyword_catalog.children[0].key and generated[1][0]==keyword_catalog.children[5].key, "responsive retrieval retains actual length-normalized keyword scores and stable original identities"

    assert transformed.hypothesis==hypothesis and retrieved==[hypothesis], "HyDE reports retain the complete hypothesis used by retrieval"
    assert [(row.child_id,row.initial_score,row.initial_rank,row.score) for row in transformed.hits]==[(ids[2],0.1,1,9.1)], "hypothetical retrieval results retain their scores and ranks through pair scoring"
    assert pair_calls==[(question,ids[2],catalog.require(ids[2]).text,0.1)], "pair scoring retains the user's complete original question and retrieved evidence"
    pair_calls.clear()
    transformed_again=desk.query_hyde(other_question,retriever,catalog,{"category":"allowed"},2,1,hyde_scorer)
    assert transformed_again.hypothesis==other_hypothesis and retrieved==[hypothesis,other_hypothesis] and hypothesis!=other_hypothesis, "different questions retrieve and report their own hypothetical document"
    assert [(row.child_id,row.initial_score,row.initial_rank,row.score) for row in transformed_again.hits]==[(ids[2],0.05,3,9.05)], "HyDE results retain original ranks and metadata admission before final selection"
    assert pair_calls==[(other_question,ids[1],catalog.require(ids[1]).text,0.25),(other_question,ids[2],catalog.require(ids[2]).text,0.05)], "each admitted hypothetical-retrieval candidate reaches its own question's pair scorer"

@pytest.mark.skip("Part 2")
def test_dbm_parent_child_catalog(tmp_path):
    """Roundtrip domain identities, numeric child order and exact microsecond metadata."""
    sources=[Source("z","Same,\n世界"," \r\n".join("词"+str(i) for i in range(24)),"billing",1700000000123457),Source("a","Same,\n世界","词0","security",1700000000123458)]
    catalog=build_catalog(sources,parent_words=24,child_words=1)
    store=CatalogStore(tmp_path/"catalog");store.save(catalog)
    restored=CatalogStore(tmp_path/"catalog").load()
    assert restored==catalog, "dbm reopening restores the exact typed source, parent and child catalog"
    assert [row.key for row in restored.sources]==["z","a"] and restored.sources[0].label=="Same,\n世界", "source insertion order and raw multiline Unicode labels are preserved"
    assert restored.sources[0].created_us==1700000000123457 and restored.sources[1].created_us==1700000000123458, "metadata times retain exact integer microseconds rather than second precision"
    assert [row.ordinal for row in restored.children[:24]]==list(range(24)), "child ordinals use numeric domain order beyond single digits"
    assert len(restored.parents)==2 and len(restored.children)==25 and restored.children[0].text==restored.children[-1].text, "equal parent ordinals and child text in distinct sources remain distinct records"
    raw=sources[0].text.encode("utf-8")
    assert all(raw[row.start:row.end].decode("utf-8")==row.text for row in restored.children if row.source_key=="z"), "stored child boundaries remain exact original UTF8 byte intervals"
    replacement=build_catalog([Source("only","Replacement","final small","api",13)],parent_words=5,child_words=3)
    store.save(replacement)
    assert store.load()==replacement and len(store.load().children)==1, "replacing the catalog removes obsolete namespaced records"
    empty=build_catalog([]);store.save(empty)
    assert store.load()==empty and store.load().sources==(), "an explicitly saved empty catalog remains loadable"
    raw_catalog=build_catalog([Source("raw","Raw source","evidence \t\r\n","policy",17)],parent_words=2,child_words=1)
    store.save(raw_catalog)
    assert store.load()==raw_catalog, "source text outside indexed intervals remains exact catalog payload"
    unindexed=build_catalog([Source("blank","Unindexed source"," \r\n\t","archive",19)],parent_words=2,child_words=1)
    store.save(unindexed)
    assert store.load()==unindexed and store.load().sources[0].text==" \r\n\t", "unindexed source records retain their raw payload and provenance"

@pytest.mark.skip("Part 3")
def test_source_lexical_pair_features():
    """Implement independent ordered phrase, early-position and source composite features."""
    scorer=SourceLexicalScorer()
    detail=scorer.breakdown("refund of policy refund policy","refund policy refund policy padding padding padding",0.03)
    assert (detail.term_overlap,detail.bigram_matches,detail.position_boost)==(2,2,1.0), "source features distinguish unique whole terms, ordered unique query phrases and first positions"
    assert math.isclose(detail.total,7.15,rel_tol=0,abs_tol=1e-14), "the composite retains all four declared source weights"
    filtered=scorer.breakdown("refund of policy","refund policy extra extra extra",0)
    assert filtered.bigram_matches==1 and filtered.term_overlap==2, "ordered phrase neighbors come from the stopword-filtered query list"
    repeated=scorer.breakdown("refund refund refund","refund refund refund extra extra extra",0)
    assert repeated.term_overlap==1 and repeated.bigram_matches==1 and repeated.position_boost==0.5, "repeated words and repeated phrase occurrences do not multiply unique feature support"
    substring=scorer.breakdown("rate","prorated padding padding padding",0.2)
    assert substring.term_overlap==0 and substring.position_boost==0.5 and substring.total==1.5, "whole-token term support and source substring-position support remain distinct"
    unicode=scorer.breakdown("x","界界x123456",0)
    assert unicode.position_boost==0.5 and unicode.term_overlap==0, "the early-position boundary uses Python characters rather than UTF8 bytes"
    assert scorer.breakdown("x","abcx12345",0).position_boost==0, "an occurrence exactly at the first-third boundary earns no position credit"
    assert scorer.breakdown("policy","policy. nothing nothing",0).term_overlap==0, "source punctuation is retained in whole-token matching"
    assert scorer.breakdown("the of is","refund policy",0.4).total==2.0, "a stopword-only query retains only the supplied initial-score component"
    catalog=build_catalog([Source("a","A","unrelated unrelated extra","x",1),Source("b","B","refund policy evidence retained","x",2)],parent_words=9,child_words=9)
    ids=[row.key for row in catalog.children]
    result=SearchDesk().query("refund policy",[(ids[0],0.03),(ids[1],0.001)],catalog,{},2,1,scorer)
    assert result[0].child_id==ids[1] and result[0].score==scorer.breakdown("refund policy",catalog.children[1].text,0.001).total, "the independent lexical scorer is actually injected into the repaired candidate service"
    mixed=scorer.breakdown("ReFuNd OF PoLiCy","REFUND policy extra extra extra",0.03)
    assert mixed==scorer.breakdown("refund of policy","refund policy extra extra extra",0.03) and mixed.term_overlap==2 and mixed.bigram_matches==1, "mixed-case queries and texts retain source lowercase feature semantics"

@pytest.mark.skip("Part 4")
def test_csv_query_batch_reports():
    """Report query-owned original ranks and exact scores before the next batch arrives."""
    catalog=build_catalog([Source("z","Billing,\n\"世界\"","one two three four five","x",1)],parent_words=3,child_words=2)
    ids=[row.key for row in catalog.children]
    async def scenario():
        state={"pulled":0,"closed":False}
        batches=[("q,first",[ScoredHit(ids[1],0.03,math.nextafter(1.0,math.inf),41),ScoredHit(ids[0],0.01,0.12345678901234568,7)]),("q-second",[ScoredHit(ids[2],0.4,-0.125,95)])]
        async def source():
            try:
                for batch in batches:
                    state["pulled"]+=1;yield batch
            finally:state["closed"]=True
        stream=stream_batches(source(),catalog)
        first=await stream.__anext__()
        first_rows=list(csv.DictReader(io.StringIO(first,newline="")))
        assert state["pulled"]==1 and len(first_rows)==2, "a completed query report is available before the next query batch is pulled"
        rest=[fragment async for fragment in stream]
        rows=list(csv.DictReader(io.StringIO(first+"".join(rest),newline="")))
        assert len(rows)==3 and [row["query_id"] for row in rows]==["q,first","q,first","q-second"], "each CSV result belongs to its own query batch without repeated header records"
        assert [int(row["initial_rank"]) for row in rows]==[41,7,95], "reported initial ranks remain original retrieval metadata rather than rerank positions or a global counter"
        assert [float(row["rerank_score"]) for row in rows]==[math.nextafter(1.0,math.inf),0.12345678901234568,-0.125], "score text preserves binary64 ordering precision across reports"
        assert [row["doc_id"] for row in rows]==[ids[1],ids[0],ids[2]] and [int(row["parent_id"]) for row in rows]==[0,0,1], "CSV projection preserves original child identity and source-local parent metadata"
        assert all(row["source_label"]=="Billing,\n\"世界\"" for row in rows) and state["closed"], "the given CSV encoder preserves raw multiline source labels and source ownership closes"
        async def empty_first():
            yield "empty",[]
            yield "nonempty",[ScoredHit(ids[0],0,0.0,2)]
        empty_rows=list(csv.DictReader(io.StringIO("".join([piece async for piece in stream_batches(empty_first(),catalog)]),newline="")))
        assert len(empty_rows)==1 and empty_rows[0]["query_id"]=="nonempty", "an empty first query still permits one header and a later complete report"
        empty_state={"pulled":0}
        async def empty_report_source():
            for batch in [("empty",[]),("later",[ScoredHit(ids[0],0,0.0,2)])]:
                empty_state["pulled"]+=1
                yield batch
        empty_stream=stream_batches(empty_report_source(),catalog)
        empty_report=await empty_stream.__anext__()
        empty_parser=csv.DictReader(io.StringIO(empty_report,newline=""))
        assert empty_state["pulled"]==1 and empty_parser.fieldnames==["query_id","doc_id","initial_rank","rerank_score","parent_id","source_label"] and list(empty_parser)==[], "an empty completed first query emits its header before a later batch is pulled"
        await empty_stream.aclose()
        state["closed"]=False;state["pulled"]=0
        early=stream_batches(source(),catalog);await early.__anext__();await early.aclose()
        assert state=={"closed":True,"pulled":1}, "client closure does not consume or report a future query batch"
    asyncio.run(scenario())

@pytest.mark.skip("Part 5")
def test_parent_context_match_tree():
    """Expand original child hits into source-separated parent blocks with nested matches."""
    text=" ".join("w"+str(i) for i in range(24))+" 终"
    catalog=build_catalog([Source("z","same",text,"x",1),Source("a","same",text,"x",2)],parent_words=10,child_words=4)
    by={(row.source_key,row.parent,row.ordinal):row for row in catalog.children}
    selected=[("z",1,1,9.0,4),("z",0,2,8.0,3),("z",1,0,7.0,1),("a",0,0,6.0,4),("z",2,1,5.0,8)]
    hits=[ScoredHit(by[(source,parent,child)].key,0.1,score,rank) for source,parent,child,score,rank in selected]
    blocks=expand_parent_context(catalog,hits)
    assert [(row["source_id"],row["parent_id"]) for row in blocks]==[("z",1),("z",0),("a",0),("z",2)], "parent contexts follow first selected child order with source-scoped parent identity"
    assert len(blocks)==4 and [len(row["matches"]) for row in blocks]==[2,1,1,1], "multiple selected children attach to one complete parent context without duplicating that context"
    assert [row["child_id"] for row in blocks[0]["matches"]]==[by[("z",1,1)].key,by[("z",1,0)].key], "nested child matches retain selected-hit order rather than catalog child order"
    assert [row["score"] for row in blocks[0]["matches"]]==[9.0,7.0] and [row["initial_rank"] for row in blocks[0]["matches"]]==[4,1], "nested match evidence retains each original score and retrieval rank"
    assert blocks[1]["text"]==blocks[2]["text"] and blocks[1]["source_id"]!=blocks[2]["source_id"], "equal parent text across sources is not a shared context identity"
    assert blocks[-1]["matches"][0]["text"]=="终" and blocks[-1]["matches"][0]["end"]==len(text.encode("utf-8")), "the clipped final child keeps its actual original byte extent"
    raw=text.encode("utf-8")
    assert all(raw[row["start"]:row["end"]].decode("utf-8")==row["text"] and all(row["start"]<=match["start"]<match["end"]<=row["end"] for match in row["matches"]) for row in blocks), "parent and nested child intervals refer to complete original source slices"
    assert expand_parent_context(catalog,[])==[] and len(hits)==5 and len(catalog.sources)==2, "empty selections do not export unselected parents or alter the input catalog"
    repeated_hits=[ScoredHit(hits[0].child_id,0.125,9.25,22),ScoredHit(hits[0].child_id,-0.5,-2.5,99)]
    repeated_blocks=expand_parent_context(catalog,repeated_hits)
    assert len(repeated_blocks)==1 and [(match["child_id"],match["score"],match["initial_rank"]) for match in repeated_blocks[0]["matches"]]==[(hits[0].child_id,9.25,22),(hits[0].child_id,-2.5,99)], "each selected hit occurrence retains its own nested evidence"
