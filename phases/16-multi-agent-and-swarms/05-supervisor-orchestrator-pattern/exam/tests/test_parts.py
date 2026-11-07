import asyncio
import copy
import json
import math
import random
import re
import time
import pytest
from leadsynth.models import Artifact,Claim,Task,Observation
from leadsynth.service import CompletionDesk
from leadsynth.workers import DurationMedian
from leadsynth.artifacts import ArtifactStore
from leadsynth.synthesis import partition_claims,merge_claim_evidence,request_targeted_followup
from leadsynth.stream import WorkerProjection
from leadsynth.wire_support import encode_markdown
from leadsynth.worktree import audit_work_tree

def sample_artifacts():
    tasks=[Task('q-z','When? ',('dates',),3),Task('q-a','What?',('names',),100),Task('q-b','Why?',('dates','names'),100)]
    outputs=[('q-z',Observation('  Alpha 年\r\n',4,1.0,['private raw'],(Claim('year','2024',('s1','s1'),'dates'),))),('q-a',Observation('Beta\n',2,3.0,['other private'],(Claim('name','system',('s2',),'names'),))),('q-b',Observation('Gamma',5,2.0,['third private'],(Claim('year','2025',('s3',),'dates'),)))]
    return tasks,outputs

def complete_fixture(count=11500):
    rng=random.Random(173);tasks=[];observations=[];expected=[];ordered=[]
    import bisect
    for i in range(count):
        seconds=rng.randrange(0,100000)/1000
        task=Task('q'+str(i),'Narrow '+str(i),('runtime',),100)
        observation=Observation('Summary '+str(i),i%110,seconds,['private '+str(i)])
        tasks.append(task);observations.append((task.question_id,observation))
        bisect.insort(ordered,seconds);n=len(ordered);middle=ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2
        expected.append((task,observation,middle))
    return tasks,observations,expected

@pytest.mark.skip('Part 1')
def test_completed_worker_receipts():
    """Repair narrow summaries, individual caps and completed-duration diagnostics."""
    tasks,observations=sample_artifacts()
    receipts=CompletionDesk().record(tasks,observations)
    assert [r['artifact'].summary for r in receipts]==['  Alpha 年\r\n','Beta\n','Gamma'], 'the lead receives original narrow summaries rather than private working context'
    assert [r['artifact'].cut for r in receipts]==[True,False,False], 'each worker retains its own declared token cap and observed usage'
    assert [r['artifact'].tokens for r in receipts]==[4,2,5], 'cut outcomes preserve actual measured token usage'
    assert [r['median'] for r in receipts]==[1.0,2.0,2.0], 'every completion contributes to the exact current runtime median'
    m=DurationMedian()
    assert [m.observe_duration(v) for v in (0,10,10,2,100)]==[0,5,10,6,10], 'duplicate and zero runtimes retain exact even and odd medians'
    tasks,observations,expected=complete_fixture()
    started=time.perf_counter();actual=CompletionDesk().record(tasks,observations)
    assert len(actual)==len(expected), 'the completion desk returns every sealed worker outcome'
    assert all(r['artifact']==Artifact(t.question_id,t.question,t.scope,o.summary,o.tokens,o.seconds,o.tokens>t.token_cap,o.claims) and r['display']==o.summary.strip() and r['median']==middle and r['timeout_threshold']==2*middle and r['slow']==(o.seconds>2*middle) for r,(t,o,middle) in zip(actual,expected)), 'complete ordered worker artifacts and timeout diagnostics remain accurate'
    elapsed=time.perf_counter()-started
    assert elapsed<0.27, 'complete sealed worker receipt batches remain responsive'

@pytest.mark.skip('Part 2')
def test_content_addressed_assignments(tmp_path):
    """Reopen exact summary objects without confusing content with assignment identity."""
    tasks,observations=sample_artifacts();artifacts=[r['artifact'] for r in CompletionDesk().record(tasks,observations)]
    same=Artifact('q-other','Other question',('dates',),artifacts[0].summary,2**60+1,-0.0,False,())
    original=artifacts+[same]
    ArtifactStore(tmp_path).save('query/一',original)
    restored=ArtifactStore(tmp_path).load('query/一')
    assert restored==original, 'reopening preserves exact artifacts usage scope claims and declared assignment order'
    assert type(restored[-1].tokens) is int and restored[-1].tokens==2**60+1 and math.copysign(1,restored[-1].seconds)==-1, 'durable usage integers and given JSON numeric values retain their original representation'
    assert len(list((tmp_path/'objects').iterdir()))==3, 'identical summary content is shared without merging distinct question assignments'
    changed=Artifact('q-other','Other question',('dates',),'Changed\n',0,0.0,False,())
    ArtifactStore(tmp_path).save('query/two',[changed])
    assert ArtifactStore(tmp_path).load('query/一')==original and ArtifactStore(tmp_path).load('query/two')==[changed], 'separate query manifests retain independent assignments to immutable content objects'
    assert len(list((tmp_path/'objects').iterdir()))==4, 'changed summary bytes produce a distinct content object'

    ArtifactStore(tmp_path).save('query/一',[changed])
    assert ArtifactStore(tmp_path).load('query/一')==[changed] and ArtifactStore(tmp_path).load('query/two')==[changed], 'saving a query replaces its ordered assignment snapshot'

@pytest.mark.skip('Part 3')
def test_scoped_conflict_synthesis(tmp_path):
    """Keep contradictory evidence visible and request only bounded targeted followups."""
    tasks,observations=sample_artifacts()
    artifacts=[r['artifact'] for r in CompletionDesk().record(tasks,observations)]
    artifacts[0]=Artifact('q-z','When?',('dates',),artifacts[0].summary,3,1,False,(Claim('year','2024',('s1','s1'),'dates'),Claim('noise','x',('s9',),'names')))
    artifacts.append(Artifact('q-c','Corroborate',('names',),'typed summary',1,4,False,(Claim('name','system',('s2','s4'),'names'),Claim('alone','yes',('s1','s1'),'names'))))
    artifacts.append(Artifact('q-cut','Cut',('dates',),'partial',99,5,True,(Claim('invented','yes',('s7','s8'),'dates'),)))
    ArtifactStore(tmp_path).save('claims',artifacts);loaded=ArtifactStore(tmp_path).load('claims')
    accepted,quarantine=partition_claims(loaded);report=merge_claim_evidence(accepted)
    assert [(r['question_id'],r['reason'],r['claim'].claim_id) for r in quarantine]==[('q-z','scope','noise'),('q-cut','cut','invented')], 'out of scope and cut-worker claims stay quarantined with original attribution'
    assert report['conflicting']==[{'claim_id':'year','alternatives':[{'value':'2024','source_ids':['s1'],'question_ids':['q-z'],'topics':['dates']},{'value':'2025','source_ids':['s3'],'question_ids':['q-b'],'topics':['dates']}]}], 'contradictory exact values remain separate with every original source and worker'
    assert [r['claim_id'] for r in report['supported']]==['name'] and [r['claim_id'] for r in report['unverified']]==['alone'], 'independent source identities determine support without duplicate-source votes'
    assert report['supported'][0]['alternatives'][0]['source_ids']==['s2','s4'], 'original source order and union remain visible across workers'
    before=copy.deepcopy(report);budgets={'year':1,'name':9};budget_before=budgets.copy()
    assert request_targeted_followup(report,budgets)==[{'claim_id':'year','scope':('dates',),'question_ids':('q-z','q-b'),'alternatives':('2024','2025'),'remaining':0}], 'a targeted followup addresses only the unresolved conflict under its own budget'
    assert request_targeted_followup(report,{'year':0})==[] and report==before and budgets==budget_before, 'exhausted followup budgets preserve unresolved evidence without mutating prior inputs'

    ordered=[Artifact('q-order-a','First',('dates',),'A',1,1,False,(Claim('ordered','v',('z','a'),'dates'),)),Artifact('q-order-b','Second',('dates',),'B',1,1,False,(Claim('ordered','v',('m','z'),'dates'),))]
    ordered_accepted,_=partition_claims(ordered)
    assert merge_claim_evidence(ordered_accepted)=={'supported':[{'claim_id':'ordered','alternatives':[{'value':'v','source_ids':['z','a','m'],'question_ids':['q-order-a','q-order-b'],'topics':['dates']}]}],'unverified':[],'conflicting':[]}, 'evidence provenance preserves first-seen union order'

@pytest.mark.skip('Part 4')
def test_worker_markdown_blocks():
    """Project sealed subanswers, missing outcomes and complete lead conflict sections."""
    tasks,observations=sample_artifacts();artifacts=[r['artifact'] for r in CompletionDesk().record(tasks,observations)]
    special=Artifact('q-b','Why?',('dates',),'A ``` literal\nline\r\n',5,2,False,())
    report={'supported':[{'claim_id':'name'}],'unverified':[{'claim_id':'alone'}],'conflicting':[{'claim_id':'year','alternatives':['2024','2025']}]}
    events=[{'kind':'worker','question_id':'q-b','question':'Why?','artifact':special,'working_context':['secret']},{'kind':'worker','question_id':'q-z','question':'When? ','artifact':artifacts[0]},{'kind':'worker','question_id':'q-a','question':'What?','artifact':None,'error':'fetch <failed>\nreason'},{'kind':'lead','required_ids':('q-z','q-a','q-b'),'report':report}]
    class Source:
        def __init__(self):self.index=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index==len(events):raise StopAsyncIteration
            event=events[self.index];self.index+=1;return event
        async def aclose(self):self.closed=True
    async def consume():
        source=Source();stream=encode_markdown(source,WorkerProjection());first=await anext(stream)
        assert source.index==1, 'the supplied driver publishes the current worker before requesting another outcome'
        blocks=[first]+[block async for block in stream]
        assert source.closed, 'the supplied driver closes the completed outcome source'
        return blocks
    blocks=asyncio.run(consume());decoded=[b.decode('utf-8') for b in blocks]
    def parse_worker(text):
        heading,question,status,*body=text.split('\n');match=re.fullmatch(r'(`{3,})text',body[0]);assert match
        fence=match.group(1);tail='\n'+fence+'\n';payload='\n'.join(body[1:]);assert payload.endswith(tail)
        return json.loads(heading[len('## Worker '):]),json.loads(question[len('Question: '):]),status[len('Status: '):],payload[:-len(tail)]
    assert [parse_worker(b) for b in decoded[:3]]==[('q-b','Why?','complete',special.summary),('q-z','When? ','cut',artifacts[0].summary),('q-a','What?','missing','fetch <failed>\nreason')], 'each Markdown block retains its own question original body and completion category'
    assert all('secret' not in b for b in decoded), 'worker working context does not enter published subanswers'
    lead=decoded[-1];lines=lead.split('\n');fence=lines[1][:-4]
    assert lead.startswith('## Lead\n') and json.loads('\n'.join(lines[2:-2]))==report, 'the lead block retains supported unverified and conflicting sections without choosing a winner'
    async def close_early():
        source=Source();stream=encode_markdown(source,WorkerProjection());await anext(stream);await stream.aclose();return source
    assert asyncio.run(close_early()).closed, 'early consumer closure uses the supplied driver cleanup contract'

    empty=Artifact('q-empty','Empty?',('names',),'',0,0)
    events[:]=[{'kind':'worker','question_id':'q-empty','question':'Empty?','artifact':empty,'error':'old diagnostic'},{'kind':'lead','required_ids':('q-empty',),'report':report}]
    empty_blocks=asyncio.run(consume())
    assert parse_worker(empty_blocks[0].decode('utf-8'))==('q-empty','Empty?','complete',''), 'an empty completed summary remains a complete worker outcome'

@pytest.mark.skip('Part 5')
def test_broad_then_narrow_dossier(tmp_path):
    """Audit genuine scope narrowing, whole-subtree budgets and leaf evidence provenance."""
    artifact=Artifact('leaf','When?',('dates',),'Original\n',2**54+1,1,False,(Claim('year','2024',('s1',),'dates'),))
    ArtifactStore(tmp_path).save('tree',[artifact]);restored=ArtifactStore(tmp_path).load('tree')[0]
    leaf={'question_id':'leaf','scope':('dates',),'budget':0,'children':[],'artifact':restored,'unresolved':()}
    sibling={'question_id':'other','scope':('names',),'budget':0,'children':[],'artifact':Artifact('other','Who?',('names',),'Name',1,1),'unresolved':()}
    branch={'question_id':'branch','scope':('dates','names'),'budget':1,'children':[leaf,sibling],'artifact':None,'unresolved':('year',)}
    root={'question_id':'root','scope':('dates','names','cost'),'budget':2,'children':[branch],'artifact':None,'unresolved':('cost',)}
    before=copy.deepcopy(root);result=audit_work_tree(root)
    assert result['findings']==[('branch-budget',('root','branch')),('branch-budget',('root',))] and result['descendants']==3, 'each branch budget counts all descendant tasks rather than depth or immediate children'
    assert [r['path'] for r in result['leaves']]==[('root','branch','leaf'),('root','branch','other')] and result['leaves'][0]['artifact']==artifact, 'leaf evidence keeps its original task attribution and complete nested path'
    assert result['unresolved']==[(('root','branch'),('year',)),(('root',),('cost',))] and root==before, 'internal unresolved claims remain explicit without rewriting the task dossier'
    broad=copy.deepcopy(root);broad['children'][0]['children'][0]['scope']=('dates','names');broad['children'][0]['children'][0]['artifact']=Artifact('sibling','Who?',('dates','names'),'wrong',1,1)
    found=audit_work_tree(broad)['findings']
    assert ('scope-not-narrower',('root','branch','leaf')) in found and ('leaf-provenance',('root','branch','leaf')) in found, 'a followup must narrow its parent and retain its own assigned leaf provenance'
    ordered_leaf={'question_id':'ordered','scope':('dates','names'),'budget':0,'children':[],'artifact':Artifact('ordered','Ordered?',('names','dates'),'S',1,1),'unresolved':()}
    ordered_root={'question_id':'ordered-root','scope':('dates','names','cost'),'budget':1,'children':[ordered_leaf],'artifact':None,'unresolved':()}
    assert ('leaf-provenance',('ordered-root','ordered')) in audit_work_tree(ordered_root)['findings'], 'leaf scope retains its original declared topic order'
