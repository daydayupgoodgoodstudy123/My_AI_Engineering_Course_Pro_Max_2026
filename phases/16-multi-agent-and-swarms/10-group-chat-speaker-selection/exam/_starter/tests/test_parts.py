"""Five sequential tasks for a deterministic group-chat selector desk.

Part1: exact terminal intake, recent context, committed-turn counts and bounded-context performance.
Part2: complete selector-input and utterance-association snapshots in SQLite.
Part3: unanswered named questions, weighted actual-turn deficits and consecutive caps.
Part4: each classified observation's own public decision fields through the supplied logfmt driver.
Part5: own cumulative agent quotas and inherited total budgets, with complete supplied reply authority.
"""
import asyncio,time
from dataclasses import replace
from fractions import Fraction
import pytest

@pytest.mark.skip('Part 1')
def test_review_chat_replay():
    """A review chat retains real approval, recent selector input and actual agent turns."""
    from floorfair.models import Speaker,Proposal,Utterance
    from floorfair.service import ChatDesk
    from floorfair.support import ReplaySelector,approval_card,render_message
    from floorfair.context import recent_selector_context
    from floorfair.fixture import conversation_fixture
    roster=(Speaker('coder'),Speaker('reviewer'),Speaker('manager'))
    selector=ReplaySelector((Proposal('coder','Please do not TERMINATE'),Proposal('reviewer','review: approved',verdict='approved'),Proposal('manager','  TERMINATE\n')))
    report=ChatDesk().run('review',roster,selector)
    assert approval_card(report)==('review','reviewer','review: approved'), 'the approval receipt consumes the reviewer evidence after a negated terminal mention'
    assert tuple(m.content for m in report.history)==('Please do not TERMINATE','review: approved','  TERMINATE\n') and report.stop=='terminal', 'only the complete trimmed terminal message closes this local review conversation'
    seed=tuple(Utterance('context','seed-'+str(i),'user',text,0)for i,text in enumerate(('obsolete','old reply','recent request','latest review request')))
    captured=ReplaySelector((Proposal('reviewer','working',reason='recent'),))
    viewed=ChatDesk().run('context',roster,captured,history=seed,window=2,max_rounds=1)
    assert viewed.records[0].context==tuple(render_message(m)for m in seed[-2:]), 'the selector reads both complete recent messages in their actual order'
    assert report.counts==(('coder',1),('reviewer',1),('manager',1)), 'only real committed utterances contribute to the agent turn shares'
    denied=ReplaySelector((Proposal('coder','not spoken',accepted=False,reason='denied'),Proposal('reviewer','',reason='allowed')))
    rejected=ChatDesk().run('reject',roster,denied,max_rounds=2)
    assert rejected.counts==(('coder',0),('reviewer',1),('manager',0)) and len(rejected.records)==3 and rejected.history[0].content=='', 'rejected selector choices remain diagnostic while an accepted empty utterance is a real turn'
    assert recent_selector_context(seed,0)==() and recent_selector_context(seed,9)==tuple(render_message(m)for m in seed), 'zero context and a window larger than history retain their declared meaning'
    args,expected=conversation_fixture();roster,history,selector=args;started=time.perf_counter()
    complete=ChatDesk().run('timed',roster,selector,history=history,window=3,max_rounds=80)
    assert complete==expected and selector.calls==80, 'the complete conversation retains every archived message real selector input choice utterance reason and count'
    elapsed=time.perf_counter()-started
    assert elapsed<0.05, 'complete recent-context chat replay remains responsive'

@pytest.mark.skip('Part 2')
def test_selector_audit_archive(tmp_path):
    """Reopened snapshots retain each selector input and its distinct linked utterance evidence."""
    from floorfair.models import Speaker,Decision,Utterance,Snapshot,Proposal
    from floorfair.service import ChatDesk
    from floorfair.support import ReplaySelector,archive_counts
    from floorfair.archive import ChatArchive
    roster=(Speaker('coder'),Speaker('reviewer'))
    run=ChatDesk().run('audit',roster,ReplaySelector((Proposal('coder','Please do not TERMINATE',private_prompt='private policy'),Proposal('reviewer',' approved\r\n',verdict='approved'))),max_rounds=2)
    snapshot=Snapshot('audit',roster,(('coder',0),('reviewer',0)),run.records);path=tmp_path/'chat.sqlite';ChatArchive(path).save(snapshot)
    assert ChatArchive(path).load('audit')==snapshot, 'reopening retains every selector input choice reason and linked utterance in actual declared order'
    loaded=ChatArchive(path).load('audit');messages=tuple(e for e in loaded.records if isinstance(e,Utterance));decisions=tuple(e for e in loaded.records if isinstance(e,Decision))
    assert tuple(m.decision_id for m in messages)==tuple(d.decision_id for d in decisions) and decisions[1].context and decisions[0].private_prompt=='private policy', 'each utterance points to its own audited decision and each decision retains its own complete selector input'
    huge=2**60+17;other=Snapshot('另一线程',(Speaker('审阅员'),),(('审阅员',huge),),(Decision('另一线程','denied','审阅员','denied',('quoted TERMINATE','\r\n'),huge,False),Decision('另一线程','accepted','审阅员','accepted',('own next input',),huge,True),Utterance('另一线程','empty','审阅员','',huge+1,'accepted')))
    ChatArchive(path).save(other)
    assert ChatArchive(path).load('另一线程')==other and archive_counts(ChatArchive(path).load('另一线程'))==(('审阅员',huge+1),), 'the supplied typed discriminator and scalar codec retain denied diagnostics exact counts empty text and Unicode'
    revised=replace(snapshot,records=snapshot.records[:2]);ChatArchive(path).save(revised)
    assert ChatArchive(path).load('audit')==revised and ChatArchive(path).load('另一线程')==other, 'replacing a conversation snapshot removes its obsolete tail while preserving other conversations'
    with pytest.raises(KeyError):ChatArchive(path).load('absent')
    ordered=replace(snapshot,thread='roster-order',roster=tuple(reversed(roster)),baseline=tuple(reversed(snapshot.baseline)),records=())
    ChatArchive(path).save(ordered)
    assert ChatArchive(path).load('roster-order')==ordered, 'declared roster order survives an empty conversation snapshot'

@pytest.mark.skip('Part 3')
def test_named_question_deficit_policy(tmp_path):
    """Only referenced answers resolve questions; actual weighted shares and caps select the next speaker."""
    from floorfair.models import Speaker,Utterance,Decision,Question,Choice,Proposal,Snapshot
    from floorfair.service import ChatDesk
    from floorfair.support import ReplaySelector,archive_counts
    from floorfair.archive import ChatArchive
    from floorfair.selection import update_question_obligations,speaker_deficits,select_next_speaker
    q1=Utterance('policy','ask1','coder','@reviewer please inspect',1,question_id='q1',addressee='reviewer');q2=replace(q1,message_id='ask2',question_id='q2',content='another independent question',turn=2)
    wrong=Utterance('policy','wrong','manager','I can answer',3,reply_to='q1');answer=Utterance('policy','answer','reviewer','specific answer',4,reply_to='q1');quoted=Utterance('policy','quote','coder','quoted: @manager answer q2?',5)
    diagnostic=Decision('policy','pick','reviewer','diagnostic',(),5,False)
    assert tuple(q.question_id for q in update_question_obligations((q1,q2,wrong)))==('q1','q2'), 'an unaddressed speaker cannot resolve another agent named question'
    pending=update_question_obligations((q1,q2,wrong,diagnostic,answer,quoted))
    assert pending==(Question('q2','policy','reviewer','ask2'),), 'only the named addressee answering the referenced question resolves that obligation'
    active=(Speaker('coder',2),Speaker('reviewer',1),Speaker('idle',100,False));counts={'coder':4,'reviewer':0,'idle':999}
    assert speaker_deficits(active,counts)==(('coder',Fraction(-2,3)),('reviewer',Fraction(5,3))), 'active weighted shares use actual committed counts and exclude inactive roster weights'
    preferred=select_next_speaker(active,{'coder':0,'reviewer':6},pending,'coder',1,2)
    assert preferred==Choice('reviewer','question:q2',Fraction(-11,3)), 'the oldest eligible unanswered named question takes priority over turn deficit'
    equal=(Speaker('first'),Speaker('second'));tie=select_next_speaker(equal,{'first':0,'second':0},(),None,0,2)
    assert tie==Choice('first','deficit',Fraction(1,2)), 'equal deficits retain the declared roster order'
    capped=select_next_speaker(active,counts,pending,'reviewer',2,2)
    assert capped.speaker=='coder' and capped.reason=='deficit' and select_next_speaker((Speaker('only'),),{'only':3},(), 'only',2,2)is None, 'the consecutive cap keeps the question pending and returns no speaker when every active candidate is blocked'
    assert select_next_speaker((Speaker('off',active=False),),{'off':10},pending,None,0,2)is None and speaker_deficits((),{})==(), 'inactive or empty rosters do not invent an eligible turn'
    with pytest.raises(ValueError,match='positive consecutive cap'):select_next_speaker(equal,{},(),None,0,0)
    roster=(Speaker('coder'),Speaker('reviewer'),Speaker('manager'))
    run=ChatDesk().run('live',roster,ReplaySelector((Proposal('coder','question',question_id='live-q',addressee='reviewer'),Proposal('manager','diagnostic only',accepted=False))),max_rounds=2)
    snapshot=Snapshot('live',roster,tuple((s.name,0)for s in roster),run.records);path=tmp_path/'policy.sqlite';ChatArchive(path).save(snapshot);loaded=ChatArchive(path).load('live')
    live=select_next_speaker(loaded.roster,dict(archive_counts(loaded)),update_question_obligations(loaded.records),'coder',1,2)
    assert live.speaker=='reviewer' and live.reason=='question:live-q' and dict(run.counts)==dict(archive_counts(loaded)), 'the policy consumes the repaired real-turn desk and reopened audit evidence rather than proposed turns'
    below_cap=select_next_speaker(equal,{'first':4,'second':4},(Question('still-pending','policy','second','ask-pending'),),'second',1,2)
    assert below_cap==Choice('second','question:still-pending',Fraction(1,2)), 'the consecutive cap measures the current streak rather than all prior speech'

@pytest.mark.skip('Part 4')
def test_public_selector_logfmt():
    """Each classified turn emits its own public logfmt evidence without the private selector prompt."""
    from floorfair.models import Speaker,Proposal,Decision,Utterance
    from floorfair.service import ChatDesk
    from floorfair.support import ReplaySelector
    from floorfair.logfmt_support import observe_turn,encode_observations,parse_line
    from floorfair.stream import DecisionProjection
    roster=(Speaker('coder'),Speaker('reviewer'))
    run=ChatDesk().run('thread 一',roster,ReplaySelector((Proposal('coder','not spoken',False,'rejected "pick"',private_prompt='SECRET-A'),Proposal('reviewer','accepted',True,'follow question\nnow',private_prompt='SECRET-B'),Proposal(None,reason='done',private_prompt='SECRET-C'))),max_rounds=3)
    decisions=tuple(e for e in run.records if isinstance(e,Decision));message=next(e for e in run.records if isinstance(e,Utterance));obs=(observe_turn(decisions[0]),observe_turn(decisions[1],message,Fraction(1,2),Fraction(0)),observe_turn(decisions[2]))
    class Source:
        def __init__(self):self.i=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.i==len(obs):raise StopAsyncIteration
            value=obs[self.i];self.i+=1;return value
        async def aclose(self):self.closed+=1
    async def collect():
        source=Source();stream=encode_observations(source,DecisionProjection());parts=[await anext(stream)]
        assert source.i==1, 'the supplied logfmt driver publishes one current observation before pulling another'
        async for part in stream:parts.append(part)
        assert source.closed==1, 'the supplied observation driver closes once'
        return b''.join(parts)
    raw=asyncio.run(collect());rows=tuple(parse_line(line)for line in raw.splitlines())
    assert len(rows)==3 and tuple(row['kind']for row in rows)==('reject','commit','stop'), 'each actual classified selection retains its own outcome phase'
    assert tuple((row['thread'],row['turn'],row['speaker'])for row in rows)==(('thread 一',0,None),('thread 一',1,'reviewer'),('thread 一',1,None)), 'public speaker and turn fields come from actual classified observations rather than proposed choices'
    assert tuple(row['reason']for row in rows)==tuple(d.reason for d in decisions) and tuple(row['deficit']for row in rows)==('0/1','1/2','0/1'), 'each observation retains its own decision reason and complete deficit evidence'
    assert b'SECRET'not in raw and all(set(row)=={'thread','turn','kind','speaker','reason','deficit'}for row in rows), 'private selector prompts stay outside the declared public evidence fields'
    projection=DecisionProjection();distinct=(replace(obs[0],thread='first thread'),replace(obs[1],thread='second thread'))
    assert tuple(projection.payload(observation)['thread']for observation in distinct)==('first thread','second thread'), 'each projection retains its current observation thread'

@pytest.mark.skip('Part 5')
def test_nested_reply_authority_and_budget():
    """Own cumulative agent quotas retain first excess evidence and inherited total budgets.

    Reply-authority evidence, identity lookup and cap validation are complete supplied dependencies.
    """
    from floorfair.models import Thread,Utterance,Decision
    from floorfair.threads import inspect_threads
    parent_ask=Utterance('parent','parent-ask','coder','parent question',1,question_id='parent-q',addressee='reviewer')
    child_records=(Decision('child','child-denied','reviewer','diagnostic',(),0,False),Utterance('child','cross','reviewer','answer parent from elsewhere',1,reply_to='parent-q'),Utterance('child','child-ask','reviewer','child question',2,question_id='child-q',addressee='coder'),Utterance('child','child-answer','coder','child answer',3,reply_to='child-q'))
    peer_records=(Utterance('peer','peer-ask','reviewer','peer question',1,question_id='peer-q',addressee='manager'),Utterance('peer','peer-wrong','coder','unrequested reply',2,reply_to='peer-q'))
    root=Thread('parent',20,(parent_ask,),(Thread('child',5,child_records),Thread('peer',4,peer_records)))
    report=inspect_threads(root);child,peer=report['children']
    assert report['pending']==(('parent-q','reviewer'),) and not report['complete'] and child['complete'] and child['pending']==(), 'a completed child conversation cannot resolve an unanswered parent question'
    assert child['issues']==(('cross','wrong-thread','parent-q'),) and peer['pending']==(('peer-q','manager'),) and peer['issues']==(('peer-wrong','wrong-addressee','peer-q'),), 'reply effect requires both the declared question thread and its named addressee'
    assert report['remaining']==14 and child['remaining']==2 and peer['remaining']==2, 'each speaking budget uses actual committed subtree utterances rather than diagnostic choices'
    tight=inspect_threads(replace(root,limit=7))
    assert tight['remaining']==1 and tuple(c['remaining']for c in tight['children'])==(1,1), 'the tightest ancestor residual constrains every descendant conversation'
    assert inspect_threads(replace(root,limit=0))['remaining']==0 and tuple(c['path']for c in report['children'])==(('parent','child'),('parent','peer')), 'exhausted nonnegative budgets and declared nested order remain observable'
    own_only=inspect_threads(Thread('clean',10,(),(Thread('open',10,(Utterance('open','own-ask','coder','unanswered child question',1,question_id='open-q',addressee='reviewer'),)),)))
    assert own_only['complete'] and own_only['pending']==() and not own_only['children'][0]['complete'], 'thread completion reflects only its own unanswered questions'
    from floorfair.models import SpeakerQuota
    quota_records=(Decision('quota','denied','coder','not speech',(),0,False),Utterance('quota','c1','coder','one',1),Utterance('quota','r1','reviewer','interleaved',2),Utterance('quota','c2','coder','two',3),Utterance('quota','r2','reviewer','again',4),Utterance('quota','c3','coder','third',5),Utterance('quota','m1','manager','single turn',6),Utterance('quota','c4','coder','fourth',7))
    quota_child=Thread('side',9,(Utterance('side','side-c1','coder','own child turn',1),),max_speaks=(('coder',1),))
    quota_root=Thread('quota',30,quota_records,(quota_child,),max_speaks=(('reviewer',3),('coder',2),('manager',1),('unused',4)))
    quota=inspect_threads(quota_root);rows=quota['speaker_quota']
    assert tuple((row.speaker,row.limit,row.used,row.remaining)for row in rows)==(('reviewer',3,2,1),('coder',2,4,0),('manager',1,1,0),('unused',4,0,4)), 'each declared agent quota retains cumulative own-thread usage and nonnegative remaining turns'
    assert tuple(row.first_excess for row in rows)==((),('c3',),(),()), 'the first excess witness is the actual agent turn immediately beyond its cumulative allowance'
    assert quota['remaining']==22 and quota['children'][0]['speaker_quota']==(SpeakerQuota('coder',1,1,0,()),), 'own agent quotas remain local while total speech budgets still include child conversations'
    exact=Thread('exact',10,(Utterance('exact','exact-c1','coder','first',1),Utterance('exact','other-r','reviewer','between',2),Utterance('exact','exact-c2','coder','at allowance',3)),max_speaks=(('coder',2),))
    zero=Thread('zero',10,(Utterance('zero','zero-first','coder','first',1),),max_speaks=(('coder',0),))
    assert inspect_threads(exact)['speaker_quota']==(SpeakerQuota('coder',2,2,0,()),) and inspect_threads(zero)['speaker_quota']==(SpeakerQuota('coder',0,1,0,('zero-first',)),), 'an exact allowance has no excess witness and a zero allowance records its first actual turn'
