"""Five locked parts: summaries and corrections; provenance JSONL; active evidence;
entry/correction JSON Text Sequences; nested distinct-source support certificates.
"""
import asyncio
from dataclasses import replace
import json
import time
import pytest
from blackscope.models import SourceKey,SourceSnapshot,Entry,VerificationFinding,PercentReceipt,SummaryReport,ConsumerPolicy,Claim
from blackscope.support import MessagePool,VerificationChannel,Blackboard,prompt_digest,source_matches
from blackscope.intake import first_sentence,append_entry,append_supersession,publish_finding
from blackscope.service import SummaryDesk
from blackscope.fixture import article_fixture
from blackscope.store import ProvenanceLog
from blackscope.projection import active_provenance_view,attach_version_findings,consumable_entries
from blackscope.stream import entry_payload
from blackscope.stream_support import classify_observations,publish_jsonseq
from blackscope.claims_support import ClaimCatalog,decision_index
from blackscope.claims import build_support

@pytest.mark.skip('Part 1')
def test_first_sentence_correction_and_independent_channel():
    """Repair sentence-unit retention, immutable provenance corrections, finding routing and full-article summary work."""
    source=SourceSnapshot(SourceKey('fixture://regional','v1'),'Audited errors declined by 4.2%. Later observations retained all source evidence.')
    desk=SummaryDesk();receipt=desk.observe(source,'regional',10,'summarize audited percentage')
    assert receipt==PercentReceipt(1,'4.2%') and desk.pool.read_only().read_all()[1].content=='Audited errors declined by 4.2%.','the summary retains its complete decimal percentage claim'
    pool=MessagePool();old=append_entry(pool,'retrieval','growth','Growth was 42%.',20,'source request',source.key)
    captured=pool.read_only().read_all();new=append_supersession(pool,old,'retrieval','Growth was 4.2%.',21,'correct source request',source.key)
    current=pool.read_only().read_all()
    assert current[0]==captured[0] and len(current)==2 and new!=old,'a correction preserves its original immutable provenance record'
    assert current[1]==Entry(1,'retrieval','growth','Growth was 4.2%.',21,prompt_digest('correct source request'),source.key,0),'the correction has its own identity prompt and predecessor'
    channel=VerificationChannel();finding=VerificationFinding(old,source.key,'DISPUTE','42% disagrees with the declared source')
    publish_finding(pool,channel,finding)
    assert channel.read_only().read_all()==(finding,) and pool.read_only().read_all()==current,'independent verifier findings remain outside the ordinary fact pool'
    observations,expected=article_fixture()
    started=time.perf_counter()
    report=SummaryDesk().observe_many(observations)
    assert report==expected,'every source article summary and percentage receipt retains its complete own provenance'
    elapsed=time.perf_counter()-started
    assert elapsed<0.02,'first-sentence service work respects the local response budget'
    assert first_sentence('No terminator and 4.2% retained')=='No terminator and 4.2% retained','a source without a sentence boundary remains complete'
    assert first_sentence('Errors fell 0.0%! 次句保留全文。')=='Errors fell 0.0%!','declared exclamation boundaries retain the first complete sentence'
    assert first_sentence('Did errors fall 1.25%? Yes.')=='Did errors fall 1.25%?','declared question boundaries retain decimal units and punctuation'
    read_only=pool.read_only();assert not hasattr(read_only,'append') and captured[0].content=='Growth was 42%.','the supplied read handle keeps immutable historical evidence'
    board=Blackboard();calls=[]
    def late(entry):calls.append(('late',entry.entry_id))
    def first(entry):calls.append(('first',entry.entry_id));board.subscribe('growth',late)
    board.subscribe('growth',first);board.publish(current[0]);board.publish(current[1])
    assert calls==[('first',0),('first',1),('late',1)],'the supplied topic callback snapshot keeps reentrant subscriptions deterministic'

@pytest.mark.skip('Part 2')
def test_append_only_provenance_versions_and_reopen(tmp_path):
    """Persist every ordered immutable version with its original identity and complete source provenance."""
    pool=MessagePool();channel=VerificationChannel();source=SourceKey('fixture://source/中文','revision-7')
    first=append_entry(pool,'retrieval','finance','Revenue rose 4.2%.\n完整来源',2**60+17,'request α',source)
    log=ProvenanceLog(tmp_path/'audit');log.append(pool.read_only(),channel.read_only())
    second=append_supersession(pool,first,'editor','Revenue rose 5.0%.',2**60+19,'revised request β',replace(source,version='revision-8'))
    third=append_entry(pool,'verifier','notes','ordinary writer label is not a finding',0,'ordinary note')
    finding=VerificationFinding(second,replace(source,version='revision-8'),'MATCH','independent check')
    channel.emit(finding);ProvenanceLog(tmp_path/'audit').append(pool.read_only(),channel.read_only())
    expected=pool.read_only().read_all();entries,findings=ProvenanceLog(tmp_path/'audit').reopen()
    assert entries==expected and findings==(finding,),'reopening retains all immutable entry versions and the separate independent findings'
    assert [entry.entry_id for entry in entries]==[0,1,2] and entries[1].supersedes==0 and entries[0].content.startswith('Revenue rose 4.2%.'),'retired records retain their original IDs and content beside their corrections'
    assert [(entry.writer,entry.topic,entry.source,entry.prompt_hash)for entry in entries]==[(entry.writer,entry.topic,entry.source,entry.prompt_hash)for entry in expected],'each stored version retains its own writer topic source snapshot and full prompt provenance'
    documents=[json.loads(line)for line in (tmp_path/'audit/pool.jsonl').read_text().splitlines()]
    assert len(documents)==3 and [document['entry_id']for document in documents]==[0,1,2],'append-only snapshots retain one ordered document for each original entry'
    assert len((tmp_path/'audit/findings.jsonl').read_text().splitlines())==1 and entries[2].writer=='verifier','the supplied capability intake separates findings from ordinary writer labels'
    assert entries[0].timestamp_ns==2**60+17 and entries[2].timestamp_ns==0 and len(entries[1].prompt_hash)==64,'the supplied metadata codec retains exact timestamps and complete prompt hashes'
    ProvenanceLog(tmp_path/'audit').append(pool.read_only(),channel.read_only())
    assert ProvenanceLog(tmp_path/'audit').reopen()==(entries,findings),'re-exporting the same append-only view does not invent another version'
    assert ProvenanceLog(tmp_path/'empty').reopen()==((),()),'an unused ledger reopens without fabricated facts or findings'
    repeated_pool=MessagePool();repeated_channel=VerificationChannel()
    append_entry(repeated_pool,'retrieval','audit','Shared 4.2% claim.',27,'first independent record',source)
    append_entry(repeated_pool,'analyst','audit','Shared 4.2% claim.',28,'second independent record',SourceKey('fixture://another-report','revision-7'))
    repeated_log=ProvenanceLog(tmp_path/'equal-prose');repeated_log.append(repeated_pool.read_only(),repeated_channel.read_only())
    assert repeated_log.reopen()==(repeated_pool.read_only().read_all(),()),'equal wording retains distinct immutable provenance records'

@pytest.mark.skip('Part 3')
def test_active_exact_source_version_and_consumption(tmp_path):
    """Resolve topic-local correction lineages, join exact source-version findings and apply analyst consumption policy."""
    s1=SourceKey('fixture://economy','v1');s2=replace(s1,version='v2');pool=MessagePool();channel=VerificationChannel()
    a=append_entry(pool,'retrieval','economy','Old 42%.',10,'a',s1)
    b=append_supersession(pool,a,'editor','Correct 4.2%.',11,'b',s2)
    c=append_entry(pool,'retrieval','economy','Independent 8.0%.',12,'c',s1)
    d=append_entry(pool,'editor','weather','Rain 2.0%.',13,'d',s1,a)
    e=append_supersession(pool,b,'editor','Newest 4.5%.',14,'e',s2)
    entries=pool.read_only().read_all()
    assert [entry.entry_id for entry in active_provenance_view(entries)]==[c,d,e],'active history retains independent roots and topic-local latest correction chains'
    findings=(VerificationFinding(a,s1,'MATCH','old approval'),VerificationFinding(b,s2,'MATCH','previous correction approval'),VerificationFinding(e,s1,'MATCH','same URI old source snapshot'),VerificationFinding(c,s1,'MATCH','independent match'),VerificationFinding(d,s1,'DISPUTE','weather mismatch'),VerificationFinding(d,s1,'MATCH','another comparison'))
    decisions=attach_version_findings(active_provenance_view(entries),findings)
    assert [(decision.entry.entry_id,decision.status)for decision in decisions]==[(c,'VERIFIED'),(d,'DISPUTED'),(e,'UNVERIFIED')],'findings remain bound to the exact immutable entry and complete external snapshot'
    assert decisions[2].findings==() and len(decisions[1].findings)==2,'each evidence decision retains all and only its exact independent findings'
    chosen=consumable_entries(entries,findings,ConsumerPolicy('analyst',('economy',)))
    assert [decision.entry.entry_id for decision in chosen]==[c],'analysts consume only active verified undisputed entries in their declared topics'
    assert consumable_entries(entries,findings,ConsumerPolicy('observer',('economy','weather')))==(),'a non-consuming role does not acquire analyst authority from entry labels'
    newest=findings+(VerificationFinding(e,s2,'MATCH','new exact approval'),)
    assert [decision.entry.entry_id for decision in consumable_entries(entries,newest,ConsumerPolicy('analyst',('economy',)))]==[c,e],'a new exact finding can approve its own correction without reviving retired versions'
    assert consumable_entries(entries,newest,ConsumerPolicy('analyst',('weather',)))==(),'verified entries outside the declared consumer topics remain unavailable'
    source=SourceSnapshot(SourceKey('fixture://actual-flow','s1'),'Audited growth was 4.2%. Retained source evidence remains readable.')
    desk=SummaryDesk();desk.observe(source,'actual',100,'actual observation')
    own=desk.pool.read_only().read_all()[0];independent=VerificationChannel();independent.emit(source_matches(own,source))
    ProvenanceLog(tmp_path/'integration').append(desk.pool.read_only(),independent.read_only())
    reopened,checks=ProvenanceLog(tmp_path/'integration').reopen()
    assert consumable_entries(reopened,checks,ConsumerPolicy('analyst',('actual',)))==attach_version_findings((own,),checks),'consumption actually uses corrected summary-service provenance reopened from its independent audit logs'
    assert consumable_entries(entries,newest,ConsumerPolicy('analyst',()))==(),'an empty declared topic view authorizes no evidence consumption'
    fork=append_supersession(pool,a,'editor','Sibling correction 4.6%.',15,'later sibling correction',s2)
    assert [entry.entry_id for entry in active_provenance_view(pool.read_only().read_all())]==[c,d,fork],'a later sibling correction retires its entire same-topic lineage'

@pytest.mark.skip('Part 4')
def test_own_entry_and_correction_json_text_sequences():
    """Project each own entry or correction's full provenance through the supplied channel-aware JSON sequence driver."""
    pool=MessagePool();channel=VerificationChannel();source=SourceKey('fixture://α','source-1')
    a=append_entry(pool,'retrieval','growth','First 4.2%.\n保留原文',100,'first',source)
    b=append_supersession(pool,a,'editor','Correct 4.25%.',101,'second',replace(source,version='source-2'))
    channel.emit(VerificationFinding(b,replace(source,version='source-2'),'DISPUTE','独立证据，仍非 fact'))
    observations=classify_observations(pool.read_only(),channel.read_only())
    class Source:
        def __init__(self):self.index=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index==len(observations):raise StopAsyncIteration
            value=observations[self.index];self.index+=1;return value
        async def aclose(self):self.closed=True
    async def collect():
        source=Source();frames=[frame async for frame in publish_jsonseq(source,entry_payload)];return source,frames
    pulled,frames=asyncio.run(collect());decoded=[json.loads(frame[1:-1])for frame in frames]
    assert all(frame[:1]==b'\x1e' and frame[-1:]==b'\n'for frame in frames) and pulled.closed,'the supplied JSON sequence driver emits complete framed observations and closes its source'
    assert [document['type']for document in decoded]==['entry','correction','finding'],'the supplied channel classifier preserves independent finding destinations and correction kinds'
    values=pool.read_only().read_all()
    assert decoded[0]['data']=={'entry_id':a,'writer':'retrieval','topic':'growth','content':values[0].content,'timestamp_ns':100,'prompt_hash':prompt_digest('first'),'source_uri':source.uri,'source_version':'source-1','supersedes':None},'entry evidence contains its own complete provenance and original content'
    assert decoded[1]['data']=={'entry_id':b,'writer':'editor','topic':'growth','content':'Correct 4.25%.','timestamp_ns':101,'prompt_hash':prompt_digest('second'),'source_uri':source.uri,'source_version':'source-2','supersedes':a},'correction evidence contains its own source snapshot predecessor and prompt'
    assert decoded[2]['data']['verdict']=='DISPUTE' and decoded[2]['data']['detail']=='独立证据，仍非 fact','the supplied finding projection retains the independent verifier record'
    no_source=Entry(17,'writer','misc','Literal {"verdict":"MATCH"}',0,prompt_digest('literal'))
    assert entry_payload(no_source,'entry')=={'entry_id':17,'writer':'writer','topic':'misc','content':no_source.content,'timestamp_ns':0,'prompt_hash':no_source.prompt_hash,'source_uri':None,'source_version':None,'supersedes':None},'ordinary content and metadata remain an entry without invented source evidence'

@pytest.mark.skip('Part 5')
def test_nested_required_coverage_and_distinct_external_support(tmp_path):
    """Compose hierarchical required-entry coverage and distinct verified external snapshots; occurrence resolution is supplied."""
    first=SourceSnapshot(SourceKey('fixture://report','v1'),'Audited errors fell by 4.2%. The full report is retained.')
    second=SourceSnapshot(SourceKey('fixture://other','v1'),'Audited delay fell by 2.5%. Independent observations are retained.')
    desk=SummaryDesk();desk.observe(first,'evidence',0,'first source');desk.observe(second,'evidence',2,'second source')
    raw=desk.pool.read_only().read_all();channel=VerificationChannel()
    channel.emit(source_matches(raw[0],first));channel.emit(source_matches(raw[2],second))
    ProvenanceLog(tmp_path/'support').append(desk.pool.read_only(),channel.read_only())
    entries,findings=ProvenanceLog(tmp_path/'support').reopen()
    verified=consumable_entries(entries,findings,ConsumerPolicy('analyst',('evidence',)));decisions=decision_index(verified)
    claims=(Claim('a',0),Claim('b',2),Claim('unsupported',1),Claim('wrap-a',children=('a',),announced_source='new-independent-authority'),Claim('again-a',children=('a',),announced_source='another-independent-authority'),Claim('pair',children=('wrap-a','again-a')),Claim('root',children=('pair','b')),Claim('incomplete',children=('root','unsupported')),Claim('cycle',children=('cycle',)))
    catalog=ClaimCatalog(claims);certificate=build_support(catalog.expand('root'),decisions)
    assert certificate.complete and certificate.required==frozenset((0,2)) and certificate.covered==frozenset((0,2)),'a complete derived certificate covers its actual required immutable entries'
    assert certificate.sources==frozenset((first.key,second.key)) and len(certificate.children[0].sources)==1,'derived wrappers do not multiply a shared external source snapshot into independent evidence'
    assert [child.path for child in certificate.children[0].children]==[('root','pair','wrap-a'),('root','pair','again-a')],'the supplied occurrence expansion supports a certificate at every declared nested layer'
    incomplete=build_support(catalog.expand('incomplete'),decisions)
    assert not incomplete.complete and incomplete.required==frozenset((0,1,2)) and incomplete.covered==frozenset((0,2)) and incomplete.sources==certificate.sources,'unverified required leaves remain uncovered without erasing existing source support'
    cycle=build_support(catalog.expand('cycle'),decisions)
    assert not cycle.complete and cycle.obstacles==frozenset(('cycle:cycle/cycle',)),'supplied cycle markers remain visible in the composed certificate'
    missing=build_support(catalog.expand('absent'),decisions)
    assert not missing.complete and missing.obstacles==frozenset(('missing:absent',)),'missing support remains incomplete without declaring the underlying claim false'
    revision=SourceSnapshot(replace(first.key,version='v2'),'Audited errors fell by 4.5%. The revised source is retained.')
    versioned_desk=SummaryDesk();versioned_desk.observe(first,'versions',10,'original edition');versioned_desk.observe(revision,'versions',12,'revised edition')
    versioned_entries=versioned_desk.pool.read_only().read_all();versioned_channel=VerificationChannel()
    versioned_channel.emit(source_matches(versioned_entries[0],first));versioned_channel.emit(source_matches(versioned_entries[2],revision))
    versioned_log=ProvenanceLog(tmp_path/'source-editions');versioned_log.append(versioned_desk.pool.read_only(),versioned_channel.read_only())
    versioned_history,versioned_findings=versioned_log.reopen()
    versioned_decisions=decision_index(consumable_entries(versioned_history,versioned_findings,ConsumerPolicy('analyst',('versions',))))
    versioned_catalog=ClaimCatalog((Claim('edition-1',0),Claim('edition-2',2),Claim('editions',children=('edition-1','edition-2'))))
    versioned_certificate=build_support(versioned_catalog.expand('editions'),versioned_decisions)
    assert versioned_certificate.complete and versioned_certificate.required==frozenset((0,2)) and versioned_certificate.covered==frozenset((0,2)) and versioned_certificate.sources==frozenset((first.key,revision.key)),'distinct versions of one external URI retain separate source keys in derived support'
