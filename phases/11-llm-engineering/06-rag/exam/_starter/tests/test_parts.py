import asyncio
from dataclasses import replace
import json
import math
import re
import sqlite3
import time

import pytest
from sourceweave.models import Document, Hit, ContextBundle, Snapshot
from sourceweave.index import RAGService
from sourceweave.store import SnapshotStore
from sourceweave.answer import grounded_answer
from sourceweave.service import AnswerService
from sourceweave.evidence import Citation, FALLBACK
from sourceweave.stream import stream_markdown
from sourceweave.chunking import recursive_chunks

@pytest.mark.skip("Part 1")
def test_corpus_generation_and_context():
    """Repair source provenance and coherent corpus generations before serving context."""
    service = RAGService(words_per_chunk=3, default_k=2)
    documents = [Document("a","same name","red red first second third fourth"),Document("b","same name","violet violet final")]
    snapshot = service.replace_corpus(documents)
    bundle = service.prepare_context("violet",1)
    assert len(bundle.hits)==1 and bundle.hits[0].chunk_id==2 and bundle.hits[0].source_id=="b", "retrieved hits preserve original flat identity and source provenance"
    assert bundle.hits[0].ordinal==0 and bundle.hits[0].text=="violet violet final", "a source-local ordinal remains separate from the global chunk identity"
    assert "[Source 1] same name (chunk 2)" in bundle.prompt and "Question: violet" in bundle.prompt, "the Step5 bundle renders retrieved-local labels and the complete question"
    assert service.prepare_context("violet",0).hits==() and len(service.prepare_context("violet").hits)==2, "explicit zero and the omitted retrieval limit have distinct meanings"
    updated=service.replace_corpus([Document("new","Replacement","cobalt only")])
    assert updated.generation==2 and len(updated.chunks)==len(updated.vectors)==1 and "violet" not in updated.vocab, "reindexing replaces chunks and fitted coordinates as one generation"
    current=service.prepare_context("cobalt",1)
    assert current.generation==2 and current.hits[0].source_id=="new" and current.hits[0].text=="cobalt only", "queries after replacement use only the current source generation"
    assert snapshot.generation==1 and len(snapshot.chunks)==3, "previous immutable snapshots retain their original records"
    empty=service.replace_corpus([])
    assert empty.generation==3 and empty.chunks==empty.vectors==empty.vocab==() and service.prepare_context("anything").hits==(), "empty replacement clears the complete corpus without retaining old evidence"
    wide=RAGService()
    wide.replace_corpus([Document(str(i),"Source "+str(i)," ".join("w"+str((i*7+j)%180) for j in range(384))) for i in range(48)])
    start=time.perf_counter()
    bundles=[wide.prepare_context("w"+str(i*13)+" w"+str(i*13+1),3) for i in range(8)]
    elapsed=time.perf_counter()-start
    assert elapsed < 0.045, "queries over an indexed corpus should stay responsive"
    assert all(len(row.hits)==3 and row.generation==1 and all(hit.text in row.prompt for hit in row.hits) for row in bundles), "responsive retrieval still returns complete current context and provenance"
    assert len({row.question for row in bundles})==8 and len({row.hits[0].chunk_id for row in bundles})>1, "different questions retain their own retrieval results"

@pytest.mark.skip("Part 2")
def test_complete_snapshot_sqlite(tmp_path):
    """Persist exact ordered corpus coordinates as one atomic SQLite snapshot."""
    path=tmp_path/"corpus.sqlite"
    store=SnapshotStore(path)
    assert store.load() is None, "a new snapshot store has no committed corpus"
    service=RAGService(words_per_chunk=2)
    original=service.replace_corpus([Document("z","重复","écho 世界\r\nsame text"),Document("a","重复","same text")])
    precise=replace(original,idf=tuple(math.nextafter(value,math.inf) for value in original.idf),vectors=tuple(tuple(math.nextafter(value,math.inf) for value in vector) for vector in original.vectors))
    store.save(precise);store.close()
    store=SnapshotStore(path)
    restored=store.load()
    assert restored==precise, "reopened storage preserves ordered documents, byte spans, vocabulary, IDF and binary64 vectors exactly"
    assert [doc.key for doc in restored.documents]==["z","a"] and restored.documents[0].text=="écho 世界\r\nsame text", "document insertion order and raw Unicode CRLF text survive persistence"
    assert [chunk.source_id for chunk in restored.chunks]==["z","z","a"] and restored.chunks[1].text==restored.chunks[2].text=="same text", "identical chunk text from distinct sources is never merged"
    assert restored.chunks[0].end==len("écho 世界".encode("utf-8")), "stored spans use original UTF8 byte coordinates"
    coordinate_order=tuple(reversed(range(len(precise.vocab))))
    permuted=replace(precise,vocab=tuple(precise.vocab[i] for i in coordinate_order),idf=tuple(precise.idf[i] for i in coordinate_order),vectors=tuple(tuple(vector[i] for i in coordinate_order) for vector in precise.vectors))
    coordinate_store=SnapshotStore(tmp_path/"coordinates.sqlite")
    coordinate_store.save(permuted);coordinate_store.close()
    coordinate_store=SnapshotStore(tmp_path/"coordinates.sqlite")
    assert coordinate_store.load()==permuted, "nonalphabetical vocabulary coordinates survive a separate exact snapshot roundtrip"
    coordinate_store.close()
    signed=replace(precise,idf=tuple(-0.0 if i==0 else value for i,value in enumerate(precise.idf)))
    signed_store=SnapshotStore(tmp_path/"signed-idf.sqlite")
    signed_store.save(signed);signed_store.close()
    signed_store=SnapshotStore(tmp_path/"signed-idf.sqlite")
    signed_restored=signed_store.load()
    assert tuple(value.hex() for value in signed_restored.idf)==tuple(value.hex() for value in signed.idf), "IDF binary64 sign bits and mantissa survive a closed-store roundtrip"
    signed_store.close()
    connection=sqlite3.connect(path)
    connection.execute("CREATE TRIGGER reject_new BEFORE INSERT ON chunks WHEN NEW.source='fail' BEGIN SELECT RAISE(ABORT,'fixture rejected write'); END")
    connection.commit();connection.close()
    rejected=service.replace_corpus([Document("fail","failure","new content")])
    failed=False
    try:store.save(rejected)
    except sqlite3.DatabaseError:failed=True
    assert failed and store.load()==precise, "a failed replacement retains the entire previously committed snapshot"
    replacement=service.replace_corpus([Document("q","one","unique")])
    store.save(replacement)
    assert store.load()==replacement and len(store.load().chunks)==1, "a successful replacement removes obsolete document, term and vector rows"
    empty=service.replace_corpus([]);store.save(empty)
    assert store.load()==empty and store.load().generation==4, "an indexed empty corpus remains a committed generation rather than an absent store"
    store.close()

@pytest.mark.skip("Part 3")
def test_extractive_answer_with_original_citation():
    """Extract the first positive distinct-keyword match and its original source span."""
    def hit(identity,text,start=0):
        return Hit(identity,"doc"+str(identity),"Source "+str(identity),0,start,start+len(text.encode("utf-8")),text,0.9)
    first=hit(7,"  violet violet violet label. cobalt violet evidence wins. ",11)
    second=hit(2,"cobalt violet equally supported",100)
    bundle=ContextBundle(9,"ignored prompt suffix",(first,second),"Question: unrelated\nAnswer:")
    result=grounded_answer("What cobalt violet",bundle)
    assert result["text"]=="cobalt violet evidence wins" and result["support"]==2, "distinct query terms select evidence rather than repeated occurrences or prompt suffix text"
    citation=result["citations"][0]
    left=11+len("  violet violet violet label. ".encode("utf-8"))
    assert citation==Citation(1,7,"doc7","Source 7",left,left+len(result["text"].encode("utf-8"))), "the winner keeps original chunk identity, absolute byte span and retrieved-local display label"
    assert len(result["citations"])==1, "only the sentence actually used as evidence is cited"
    assert grounded_answer("the what is",bundle)=={"text":FALLBACK,"support":0,"citations":()}, "a question containing only source stopwords produces the declared uncited fallback"
    assert grounded_answer("missing",bundle)["text"]==FALLBACK and grounded_answer("violet",ContextBundle(1,"",(),""))["citations"]==(), "zero overlap and absent retrieval do not manufacture support"
    tied=grounded_answer("cobalt violet",ContextBundle(1,"",(second,first),""))
    assert tied["text"]==second.text and tied["citations"][0].label==1, "equal support keeps the earliest eligible retrieved sentence"
    short=hit(8,"violet. violet means a color.")
    assert grounded_answer("violet",ContextBundle(1,"",(short,),""))["text"]=="violet means a color", "stripped evidence shorter than ten Python characters is ineligible"
    unicode=hit(4,"  世界 cobalt retained.  ",23)
    answer=grounded_answer("世界 cobalt",ContextBundle(1,"",(unicode,),""))
    assert answer["text"]=="世界 cobalt retained" and answer["citations"][0].start==25 and answer["citations"][0].end==25+len(answer["text"].encode("utf-8")), "stripped evidence preserves Unicode source byte offsets"
    punctuated=grounded_answer("cobalt",ContextBundle(1,"",(hit(5,"cobalt, is punctuation-bound"),),""))
    assert punctuated["support"]==0, "source whitespace tokens retain their punctuation under this toy contract"
    service=RAGService();service.replace_corpus([Document("a","A","irrelevant amber record."),Document("b","B","violet cobalt verified evidence.")])
    integrated=AnswerService(service).answer("violet cobalt",1)
    assert integrated["text"]=="violet cobalt verified evidence" and integrated["citations"][0].source_id=="b", "the answer service composes current retrieval with independent evidence extraction"

    stopword_bundle=ContextBundle(1,"",(hit(13,"the is what are"),),"")
    assert grounded_answer("the is what",stopword_bundle)=={"text":FALLBACK,"support":0,"citations":()}, "stopword-only overlap cannot support an eligible evidence sentence"
    ten=grounded_answer("cobalt",ContextBundle(1,"",(hit(14,"cobalt yes"),),""))
    assert ten["text"]=="cobalt yes" and ten["support"]==1 and ten["citations"][0].chunk_id==14, "exactly ten stripped Python characters remain eligible evidence"

@pytest.mark.skip("Part 4")
def test_markdown_evidence_replay():
    """Replay unchanged fragments and a Markdown appendix for actually used sources."""
    refs={2:Citation(2,8,"β","quoted \"source\"\nline",3,21),1:Citation(1,4,"a","unused",0,9),3:Citation(3,6,"c","third",10,20)}
    async def scenario():
        state={"pulled":0,"closed":False}
        pieces=["Answer [", "^3] then [^", "2] repeated [^3]."]
        async def source():
            try:
                for value in pieces:
                    state["pulled"]+=1
                    yield value
            finally:state["closed"]=True
        stream=stream_markdown(source(),refs)
        first=await stream.__anext__()
        assert first==pieces[0] and state["pulled"]==1, "the first body fragment is available before later source fragments are pulled"
        output=[first]+[value async for value in stream]
        assert output[:3]==pieces and state["closed"], "body fragments remain byte-for-byte text fragments and source ownership is released"
        body="".join(output)
        assert output[-1].startswith("\n\n[^"), "a citation appendix begins with exactly two separator LF characters"
        answer,appendix=body.split("\n\n",1)
        assert answer=="".join(pieces) and appendix.endswith("\n"), "the Markdown appendix follows the unchanged answer with the declared LF separation"
        assert not appendix.endswith("\n\n"), "the citation appendix has exactly one terminal LF"
        lines=appendix.rstrip("\n").split("\n")
        labels=[int(re.match(r"\[\^(\d+)\]: ",line).group(1)) for line in lines]
        assert labels==[3,2], "only cited source labels appear once in first-use order"
        records=[json.loads(line.split(": ",1)[1]) for line in lines]
        assert records[1]=={"source":refs[2].source_name,"source_id":"β","chunk":8,"start":3,"end":21}, "footnotes preserve exact escaped source metadata and original source coordinates"
        async def plain():
            yield "literal [^0] and unmatched [^"
            yield "x]"
        assert [value async for value in stream_markdown(plain(),refs)]==["literal [^0] and unmatched [^","x]"], "unmatched or nonpositive marker text remains literal without an empty appendix"
        async def absent():
            if False:yield ""
        assert [value async for value in stream_markdown(absent(),refs)]==[], "an empty answer does not export unused retrieved sources"
        async def empty_fragments():
            for fragment in ("","retained [^2]",""):yield fragment
        replayed=[value async for value in stream_markdown(empty_fragments(),refs)]
        assert replayed[:3]==["","retained [^2]",""] and len(replayed)==4 and replayed[-1].startswith("\n\n[^2]: "), "empty source fragments retain their exact positions around a cited singleton body"
        async def unknown():yield "unsupported [^99]"
        failed=False
        try:[value async for value in stream_markdown(unknown(),refs)]
        except ValueError:failed=True
        assert failed, "an unavailable complete citation label is rejected"
        state["closed"]=False;state["pulled"]=0
        early=stream_markdown(source(),refs);await early.__anext__();await early.aclose()
        assert state=={"pulled":1,"closed":True}, "early client closure releases the source without requesting future fragments"
    asyncio.run(scenario())

@pytest.mark.skip("Part 5")
def test_boundary_first_recursive_chunks():
    """Preserve fitting boundaries, split oversized descendants and retain raw spans."""
    document=Document("doc","Sections","# Intro\n\nshort same\n\nshort same\n\n# 深入\n\none two three. four five six.\n\nseven eight nine ten eleven twelve thirteen")
    rows=recursive_chunks(document,4)
    assert [row["text"] for row in rows]==["# Intro","short same","short same","# 深入","one two three.","four five six.","seven eight nine ten","eleven twelve thirteen"], "oversized sections descend through paragraphs and sentences before bounded leaf windows"
    assert all(len(row["text"].split())<=4 for row in rows), "every emitted source chunk satisfies the declared word budget"
    assert rows[1]["start"]!=rows[2]["start"] and rows[1]["text"]==rows[2]["text"], "repeated paragraph contents retain distinct original intervals"
    raw=document.text.encode("utf-8")
    assert all(raw[row["start"]:row["end"]].decode("utf-8")==row["text"] and row["source_id"]=="doc" for row in rows), "chunk text and source identity agree with exact original UTF8 byte slices"
    assert [row["section_path"] for row in rows]==[("Intro",)]*3+[("深入",)]*5, "section metadata follows descendants without duplicating heading text"
    assert all(left["end"]<=right["start"] for left,right in zip(rows,rows[1:])), "ordered source chunks do not overlap"
    assert " ".join(" ".join(row["text"].split()) for row in rows)==" ".join(document.text.split()), "every original nonwhitespace token is covered once"
    fitting=Document("fit","F","# Whole\n\nsmall body")
    kept=recursive_chunks(fitting,4)
    assert len(kept)==1 and kept[0]["text"]==fitting.text and kept[0]["end"]==len(fitting.text.encode("utf-8")), "a complete section at the exact boundary remains one raw interval"
    noheading=Document("plain","P","same text\n\nsame text")
    plain=recursive_chunks(noheading,2)
    assert [row["text"] for row in plain]==["same text","same text"] and all(row["section_path"]==() for row in plain), "preamble paragraphs do not invent a heading or merge fitting siblings"
    assert recursive_chunks(Document("empty","E"," \n\t"),3)==[], "whitespace-only input yields no fabricated source chunk"
    failed=False
    try:recursive_chunks(document,0)
    except ValueError:failed=True
    assert failed, "a nonpositive chunk budget is rejected"

    paragraph=Document("paragraph","P","# Keep\n\nred one. blue two.")
    paragraph_rows=recursive_chunks(paragraph,4)
    assert [row["text"] for row in paragraph_rows]==["# Keep","red one. blue two."], "a fitting multi-sentence paragraph remains intact inside an oversized section"
