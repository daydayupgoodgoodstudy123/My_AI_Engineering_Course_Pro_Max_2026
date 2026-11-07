"""Five sequential role-specialization tasks over local trusted code and explicit typed replay.

Part1: structural critic, declared callable, all cases and compile-once verification.
Part2: revision-bound SQLite role records with complete supplied codec/transaction.
Part3: role-owned clarification, selective invalidation and blocked-step resume.
Part4: deterministic per-case JUnit evidence through a complete supplied driver.
Part5: nested typed SOP producer/consumer and declared-output contracts.
"""
import asyncio,time,json
from dataclasses import replace
import xml.etree.ElementTree as ET
import pytest

@pytest.mark.skip('Part 1')
def test_complete_trusted_verification():
    """A structural critic cannot replace every declared deterministic case."""
    from sopforge.models import Spec,Artifact,Case
    from sopforge.service import VerificationDesk
    from sopforge.fixture import verifier_fixture
    desk=VerificationDesk();spec=Spec('literal',0,'add_two','add_two(a,b)','sum',(Case('check',(1,2),3),))
    literal=Artifact('literal-only',0,spec.spec_id,0,'"""def add_two(a,b): return a+b"""\n')
    blocked=desk.inspect(spec,literal)
    assert blocked.critic.approved is False and blocked.verifier.executed is False and blocked.verifier.cases==(), 'literal source text does not establish a declared function for the downstream verifier'
    named=replace(spec,spec_id='named',task_name='declared_sum')
    art=Artifact('two-functions',0,named.spec_id,0,'def add_two(a,b):\n    return a+b\ndef declared_sum(a,b):\n    return a*b\n')
    bound=desk.inspect(named,art)
    assert bound.critic.approved and not bound.verifier.passed and bound.verifier.cases[0].got==2, 'verification follows the declared callable rather than another plausible function'
    cases=(Case('first',(2,2),4),Case('late',(1,2),3),Case('raises',('bad',1),0))
    late=replace(spec,spec_id='late',cases=cases)
    product=Artifact('product',0,late.spec_id,0,'def add_two(a,b):\n    if a=="bad":raise ValueError("bad input")\n    return a*b\n')
    all_cases=desk.inspect(late,product)
    assert tuple(c.case_id for c in all_cases.verifier.cases)==('first','late','raises') and tuple(c.kind for c in all_cases.verifier.cases)==('passed','failure','error') and not all_cases.verifier.passed, 'all declared cases retain independent successes mismatches and exceptions after an early success'
    args,expected=verifier_fixture();started=time.perf_counter();complete=desk.inspect(*args)
    assert complete==expected, 'complete verification retains the artifact both role reports and every declared case observation'
    elapsed=time.perf_counter()-started
    assert elapsed<0.08, 'complete immutable artifact verification remains responsive'
    counter=replace(spec,spec_id='counter',cases=(Case('one',(0,0),1),Case('two',(0,0),2),Case('three',(0,0),3)))
    counting=Artifact('counting',0,counter.spec_id,0,'counter=0\ndef add_two(a,b):\n    global counter\n    counter+=1\n    return counter\n')
    first=desk.inspect(counter,counting);second=desk.inspect(counter,counting)
    assert tuple(c.got for c in first.verifier.cases)==(1,2,3) and first==second, 'one artifact execution shares its namespace across cases and each complete verification starts fresh'
    swapped=replace(counting,revision=1,code='def add_two(a,b):\n    return 99\n')
    changed=desk.inspect(counter,swapped)
    assert changed.verifier.source_digest!=first.verifier.source_digest and tuple(c.got for c in changed.verifier.cases)==(99,99,99), 'changed source cannot inherit an older artifact callable or namespace'

    load_bad=replace(literal,artifact_id='load-failure',code='raise ValueError("module <failed>")\ndef add_two(a,b):\n    return a+b\n')
    load_report=desk.inspect(spec,load_bad)
    assert load_report.critic.approved and not load_report.verifier.executed and not load_report.verifier.passed and load_report.verifier.cases==() and load_report.verifier.load_error==('ValueError','module <failed>'), 'the supplied loader retains module execution errors without fabricating completed cases'

@pytest.mark.skip('Part 2')
def test_revision_bound_role_store(tmp_path):
    """SQLite links each artifact revision to its own complete critic and verifier records."""
    from sopforge.models import Spec,Artifact,Case,Snapshot
    from sopforge.service import VerificationDesk
    from sopforge.store import SOPStore
    huge=2**80+13;payload={'tuple':(huge,-0.0),'list':[0,None,'一\r\ntext']}
    s0=Spec('persist',0,'add_two','add_two(a,b)','old\r\n一',(Case('old',(huge,3),huge+3),),fields=(('metadata',payload),))
    s1=replace(s0,revision=1,description='new & <tag>',cases=s0.cases+(Case('nested',({'x':(1,[2,None])},0),{'expected':1}),))
    a0=Artifact('same-artifact',0,s0.spec_id,0,'def add_two(a,b):\n    return a+b\n')
    a1=Artifact('same-artifact',1,s1.spec_id,1,'def add_two(a,b):\n    if isinstance(a,dict):return {"observed":a}\n    return a*b\n')
    desk=VerificationDesk();b0=desk.inspect(s0,a0);b1=desk.inspect(s1,a1);before=Snapshot((s0,s1),(b1,b0));path=tmp_path/'sop.sqlite'
    SOPStore(path).save(before);after=SOPStore(path).load()
    assert after==before and tuple((b.artifact.artifact_id,b.artifact.revision)for b in after.bundles)==(('same-artifact',1),('same-artifact',0)), 'reopening retains ordered artifact revisions and their separate role reports'
    assert after.bundles[0].critic.approved and not after.bundles[0].verifier.passed and after.bundles[1].verifier.passed, 'critic acceptance and deterministic case evidence occupy distinct persisted role slots'
    meta=dict(after.specs[0].fields)['metadata']
    assert type(meta['tuple'])is tuple and type(meta['list'])is list and type(meta['tuple'][0])is int and meta['tuple'][0]==huge and meta['tuple'][1].hex()==(-0.0).hex(), 'the supplied typed codec retains nested argument and metadata representations exactly'
    assert after.bundles[0].verifier.cases[-1].got=={'observed':{'x':(1,[2,None])}} and after.bundles[0].artifact.code==a1.code, 'complete failure details and exact source remain available after reopening'
    invalid=replace(b1,verifier=replace(b1.verifier,source_digest=b0.verifier.source_digest))
    with pytest.raises(ValueError,match='verifier-artifact-link'):SOPStore(path).save(Snapshot((s0,s1),(invalid,)))
    assert SOPStore(path).load()==before, 'a rejected report binding leaves the supplied transaction snapshot readable'
    SOPStore(path).save(Snapshot((s0,),(b0,)))
    assert SOPStore(path).load()==Snapshot((s0,),(b0,)), 'a replacement snapshot does not reopen artifacts removed from the current dossier'

    pending=replace(s0,spec_id='planner-only',revision=7,description='await executor')
    dossier=Snapshot((s1,pending,s0),(b1,b0));SOPStore(path).save(dossier)
    assert SOPStore(path).load()==dossier, 'planner-only specifications remain in the complete dossier'

@pytest.mark.skip('Part 3')
def test_role_owned_clarification_resume(tmp_path):
    """Missing required information becomes an owning-role question and selective replay."""
    from sopforge.models import Spec,Artifact,Case,FieldRule,Step,PipelineState,Answer,Snapshot
    from sopforge.service import VerificationDesk
    from sopforge.flow import required_field_questions,apply_clarification_answer,resume_blocked_step
    from sopforge.store import SOPStore
    rules=(FieldRule('operation','planner'),FieldRule('return_type','requirements_analyst'),FieldRule('optional_style','critic',False),FieldRule('precision','planner'))
    spec=Spec('clarify',0,'add_two','add_two(a,b)','sum',(Case('probe',(1,2),3),),fields=(('operation','sum'),),rules=rules)
    good=Artifact('retained',0,spec.spec_id,0,'def add_two(a,b):\n    return a+b\n');wrong=replace(good,artifact_id='rejected',code='def add_two(a,b):\n    return a*b\n')
    desk=VerificationDesk();kept=desk.inspect(spec,good);rejected=desk.inspect(spec,wrong)
    path=tmp_path/'clarify.sqlite';SOPStore(path).save(Snapshot((spec,),(kept,rejected)));saved=SOPStore(path).load();spec=saved.specs[0];kept,rejected=saved.bundles
    state=PipelineState(spec,(spec,),(Step('build',('operation','return_type')),Step('unrelated',('operation',),kept,1,'complete'),Step('old-rejected',('return_type',),rejected,1,'rejected')))
    blocked=required_field_questions(state,'build')
    assert len(blocked.questions)==1 and blocked.questions[0].owner=='requirements_analyst' and blocked.questions[0].field=='return_type' and blocked.blocked_step=='build', 'only the missing required input produces a question addressed to its declared owning role'
    calls=[]
    def executor(current,step_id):
        calls.append((current.revision,step_id));return Artifact('resumed',current.revision,current.spec_id,current.revision,'def add_two(a,b):\n    return a+b\n')
    waiting=resume_blocked_step(blocked,'build',executor)
    assert waiting==blocked and calls==[], 'a blocked executor does not invent information or run before its answer arrives'
    q=blocked.questions[0];answer=Answer(q.question_id,q.spec_id,q.spec_revision,q.field,q.owner,'int')
    with pytest.raises(ValueError,match='active role question'):apply_clarification_answer(blocked,replace(answer,owner='planner'))
    with pytest.raises(ValueError,match='active role question'):apply_clarification_answer(blocked,replace(answer,spec_revision=1))
    with pytest.raises(ValueError,match='active role question'):apply_clarification_answer(blocked,replace(answer,question_id='unrelated'))
    revised=apply_clarification_answer(blocked,answer)
    assert revised.spec.revision==1 and dict(revised.spec.fields)=={'operation':'sum','return_type':'int'} and revised.questions==() and revised.history==(spec,revised.spec), 'a matching role answer creates the next specification revision while preserving prior fields'
    slots={s.step_id:s for s in revised.steps}
    assert slots['unrelated'].bundle is kept and slots['unrelated'].runs==1 and slots['old-rejected'].bundle is None and slots['old-rejected'].runs==1, 'only field-dependent artifact and report slots are invalidated by clarification'
    resumed=resume_blocked_step(revised,'build',executor);again=resume_blocked_step(resumed,'build',executor)
    assert calls==[(1,'build')] and resumed==again and resumed.blocked_step is None and resumed.steps[0].status=='complete' and resumed.steps[0].bundle.verifier.passed, 'only the ready blocked step resumes once through the repaired critic and deterministic verifier'
    def plausible(current,step_id):return Artifact('plausible',1,current.spec_id,current.revision,'def add_two(a,b):\n    return a*b\n')
    refused=resume_blocked_step(revised,'build',plausible)
    assert refused.steps[0].bundle.critic.approved and not refused.steps[0].bundle.verifier.passed and refused.steps[0].status=='rejected', 'critic acceptance cannot substitute for failed deterministic evidence after resume'
    zero_spec=replace(spec,fields=(('operation',0),))
    zero_state=replace(state,spec=zero_spec,history=(zero_spec,));ready=required_field_questions(zero_state,'unrelated')
    assert ready.questions==() and ready.steps[1].bundle is kept, 'the supplied presence helper treats an explicit zero field as provided and retains unrelated completed work'

    multi=replace(state,steps=state.steps+(Step('later',('precision',)),))
    multi=required_field_questions(required_field_questions(multi,'build'),'later')
    other_q=next(q for q in multi.questions if q.step_id=='later')
    multi_revised=apply_clarification_answer(multi,answer)
    assert len(multi_revised.questions)==1 and multi_revised.questions[0].step_id=='later' and multi_revised.questions[0].field=='precision' and multi_revised.questions[0].owner=='planner' and multi_revised.questions[0].spec_revision==1 and multi_revised.questions[0].question_id!=other_q.question_id, 'unanswered role questions survive another step clarification with renewed specification identity'
    stale_other=Answer(other_q.question_id,other_q.spec_id,other_q.spec_revision,other_q.field,other_q.owner,8)
    with pytest.raises(ValueError,match='active role question'):apply_clarification_answer(multi_revised,stale_other)
    renewed=multi_revised.questions[0];current_other=replace(stale_other,question_id=renewed.question_id,spec_revision=renewed.spec_revision)
    both=apply_clarification_answer(multi_revised,current_other)
    assert both.questions==() and both.spec.revision==2 and dict(both.spec.fields)['return_type']=='int' and dict(both.spec.fields)['precision']==8, 'each matching outstanding role answer advances the bounded replay without losing earlier clarified fields'

    with pytest.raises(ValueError,match='another step is blocked'):resume_blocked_step(blocked,'unrelated',executor)

@pytest.mark.skip('Part 4')
def test_completed_verifier_junit():
    """JUnit uses every completed deterministic case and its own value or exception evidence."""
    from sopforge.models import Spec,Artifact,Case
    from sopforge.service import VerificationDesk
    from sopforge.stream import SOPProjection
    from sopforge.wire_support import encode_junit
    spec=Spec('junit一',0,'add_two','add_two(a,b)','cases',(Case('pass',(2,2),4),Case('mismatch',(1,2),3),Case('boom',('boom',0),0),Case('empty',('empty',0),0)))
    code='def add_two(a,b):\n    if a=="boom":raise ValueError(\'<broken>&"quoted"\')\n    if a=="empty":raise RuntimeError()\n    return a*b\n'
    first=VerificationDesk().inspect(spec,Artifact('junit-code',0,spec.spec_id,0,code))
    other=Spec('other',1,'total_sum','total_sum(a,b)','second',(Case('zero',(0,0),0),));second=VerificationDesk().inspect(other,Artifact('other-code',1,other.spec_id,1,'def total_sum(a,b):\n    return a+b\n'))
    class Source:
        def __init__(self):self.i=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.i==2:raise StopAsyncIteration
            item=(first,second)[self.i];self.i+=1;return item
        async def aclose(self):self.closed+=1
    async def collect():
        source=Source();stream=encode_junit(source,SOPProjection());parts=[await anext(stream)]
        assert source.i==0, 'the supplied JUnit driver opens the document before consuming a completed verification'
        parts.extend((await anext(stream),await anext(stream)))
        assert source.i==1, 'the supplied JUnit driver publishes a current case before pulling a later verification'
        async for part in stream:parts.append(part)
        assert source.closed==1, 'the supplied JUnit driver closes its completed-result source once'
        return b''.join(parts)
    root=ET.fromstring(asyncio.run(collect()));suites=root.findall('testsuite')
    assert len(suites)==2 and suites[0].attrib=={'name':'junit一@0','tests':'4','failures':'1','errors':'2'} and suites[1].attrib=={'name':'other@1','tests':'1','failures':'0','errors':'0'}, 'JUnit suite counts follow actual completed case evidence rather than critic approval'
    cases=suites[0].findall('testcase')
    assert [c.attrib['name']for c in cases]==['pass','mismatch','boom','empty'] and cases[0].find('failure')is None and cases[0].find('error')is None, 'all declared cases remain ordered including successful cases without synthetic issues'
    assert cases[1].find('failure').attrib['message']=='expected 3, got 2' and cases[1].find('failure').text=='args=(1, 2)', 'mismatch diagnostics retain the deterministic expected actual and argument evidence'
    assert cases[2].find('error').attrib['message']=='ValueError: <broken>&"quoted"' and cases[3].find('error').attrib['message']=='RuntimeError: ', 'the supplied outcome classification retains exception evidence independently of message content'
    assert suites[1].find('testcase').attrib=={'classname':'other@1:total_sum','name':'zero'}, 'each completed testcase retains its specification revision and declared function identity'

    entries=SOPProjection().case_entries(first)
    assert tuple(e.body for e in entries[2:])==("args=('boom', 0)","args=('empty', 0)"), 'each exception retains its own completed call arguments'
    independent=VerificationDesk().inspect(other,replace(second.artifact,revision=7))
    assert tuple(e.classname for e in SOPProjection().case_entries(independent))==('other@1:total_sum',), 'case identity uses the specification revision independently of artifact revision'

@pytest.mark.skip('Part 5')
def test_nested_role_artifact_contracts():
    """Every nested SOP boundary consumes typed producer output and exposes declared artifacts."""
    from sopforge.models import Spec,Artifact,Case,RoleRecord,SOPStage
    from sopforge.service import VerificationDesk
    from sopforge.sop import audit_sop
    spec=Spec('nested',0,'add_two','add_two(a,b)','sum',(Case('case',(1,2),3),));artifact=Artifact('nested-code',0,spec.spec_id,0,'def add_two(a,b):\n    return a+b\n');bundle=VerificationDesk().inspect(spec,artifact)
    records=(RoleRecord('spec-0','planner','spec',spec),RoleRecord('artifact-0','executor','artifact',artifact),RoleRecord('critic-0','critic','critic-report',bundle.critic),RoleRecord('verifier-0','verifier','verifier-report',bundle.verifier))
    critique=SOPStage('review','critic',(('spec','spec-0'),('artifact','artifact-0')),(('critique','critic-0'),),('critique',))
    verify=SOPStage('check','verifier',(('spec','spec-0'),('artifact','artifact-0')),(('verification','verifier-0'),),('verification',))
    execute=SOPStage('build','executor',(('spec','spec-0'),),(('artifact','artifact-0'),),('artifact',),(critique,verify))
    root=SOPStage('plan','planner',(),(('spec','spec-0'),),('spec',),(execute,));good=audit_sop(root,records)
    assert good['issues']==() and good['visible_outputs']==(('spec','spec-0'),) and good['children'][0]['visible_outputs']==(('artifact','artifact-0'),), 'valid typed role outputs cross only their declared nested export boundary'
    assert tuple(c['path']for c in good['children'][0]['children'])==(('plan','build','review'),('plan','build','check')) and all(c['issues']==()for c in good['children'][0]['children']), 'every child role is audited in declared SOP order with its complete path'
    bad_verify=replace(verify,inputs=(('spec','spec-0'),('artifact','critic-0')))
    bad_root=replace(root,children=(replace(execute,children=(critique,bad_verify)),));bad=audit_sop(bad_root,records)
    assert (('plan','build','check'),'input-contract','artifact')in bad['children'][0]['children'][1]['issues'], 'a critic report cannot fulfill the executor artifact input at a verifier boundary'
    missing=replace(execute,inputs=(),exposes=('artifact','invented'))
    result=audit_sop(replace(root,children=(missing,)),records)['children'][0]
    assert (('plan','build'),'missing-input','spec')in result['issues'] and (('plan','build'),'unproduced-export','invented')in result['issues'] and result['visible_outputs']==(('artifact','artifact-0'),), 'a nested stage cannot invent a required input or expose an unproduced artifact'
    wrong_output=replace(verify,outputs=(('verification','critic-0'),))
    result=audit_sop(replace(root,children=(replace(execute,children=(wrong_output,)),)),records)['children'][0]['children'][0]
    assert (('plan','build','check'),'output-contract','verification')in result['issues'] and result['visible_outputs']==(), 'critic and verifier outputs have distinct producer and schema contracts even when both approve'
    lie=RoleRecord('false-artifact','executor','artifact',bundle.critic);bad=replace(execute,outputs=(('artifact','false-artifact'),))
    result=audit_sop(replace(root,children=(bad,)),records+(lie,))['children'][0]
    assert (('plan','build'),'output-contract','artifact')in result['issues'], 'a declared kind label cannot replace the actual typed role payload'
    stale=replace(bundle.verifier,artifact_revision=9)
    stale_record=RoleRecord('stale-report','verifier','verifier-report',stale)
    stale_stage=replace(verify,outputs=(('verification','stale-report'),))
    result=audit_sop(replace(root,children=(replace(execute,children=(stale_stage,)),)),records+(stale_record,))['children'][0]['children'][0]
    assert (('plan','build','check'),'stage-report-artifact-link','verification')in result['issues'], 'the supplied link check binds a typed report to the actual consumed artifact revision'

    foreign=RoleRecord('spec-from-executor','executor','spec',spec)
    foreign_input=replace(execute,inputs=(('spec','spec-from-executor'),),children=())
    scoped=audit_sop(replace(root,children=(foreign_input,)),records+(foreign,))['children'][0]
    assert (('plan','build'),'input-contract','spec')in scoped['issues'], 'a typed input still requires its declared producing role'
    hidden=audit_sop(replace(root,children=(replace(execute,exposes=(),children=()),)),records)['children'][0]
    assert hidden['visible_outputs']==() and hidden['issues']==(), 'unexposed valid outputs stay inside their own SOP stage'
