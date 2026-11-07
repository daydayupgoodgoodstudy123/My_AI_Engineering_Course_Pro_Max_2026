"""Five locked parts: local deployment, durable rollouts, finite mixer, CSV and nested certificates."""
import asyncio,csv,io,json,struct,time
from dataclasses import replace
from fractions import Fraction
import pytest
from ctdegrid.models import *
from ctdegrid.primitives import encode_local_observation,local_actor,candidate_distance
from ctdegrid.service import GridDesk
from ctdegrid.fixture import inspection_requests,expected_inspection
from ctdegrid.store import RolloutArchive
from ctdegrid.mixing import mix_joint_value,validate_monotonicity,joint_action_oracle
from ctdegrid.mix_support import training_features
from ctdegrid.stream import serve
from ctdegrid.wire_support import CSVWriter,FIELDS
from ctdegrid.expression_support import ExpressionCatalog
from ctdegrid.structure import audit_expression

def example_request():
    return GridRequest('joint,α','episode,α',7,World(7,((1,1),(2,2)),((1,2),(2,3))),((1,2),(2,3)),('north','west'))

def reopened_report(tmp_path,requests):
    report=GridDesk().inspect(requests);path=tmp_path/'rollout.bin';a=RolloutArchive(path);a.save(report);a.close()
    b=RolloutArchive(path);restored=b.reopen();b.close();return restored

@pytest.mark.skip(reason="Part 1")
def test_part1_local_joint_inspection():
    """Repair canonical local lookup, decision independence, both collectors and complete empty-grid inspection cost."""
    raw=Observation('agent0',7,(1,2),(5,4));table={raw:(ActionValue('stay',-2.),ActionValue('east',3.))}
    observation=encode_local_observation(raw)
    chosen=local_actor(observation,table,'north')
    assert chosen=='east','the declared canonical local Q row determines this actor decision'
    desk=GridDesk();request=example_request();single=desk.inspect((request,))
    assert single==expected_inspection((request,)),'all local Q, action and joint training fields belong to the actual request'
    assert single.transitions[0].collected==((1,2),(2,3)) and single.transitions[0].rewards==(1.,1.),'one joint turn retains both distinct actual collectors'
    other=replace(request,uid='hidden-other',world=replace(request.world,positions=((1,1),(6,6))),critic_hints=('south','east'))
    assert desk.inspect((other,)).transitions[0].actions[0]==single.transitions[0].actions[0],'identical local input and Q values ignore changed hidden state and critic hint'
    shared=GridRequest('shared','same',0,World(4,((1,0),(1,2)),((1,1),)),((1,1),(1,1)))
    shared_result=desk.inspect((shared,)).transitions[0]
    assert shared_result.rewards==(1.,0.) and shared_result.done,'a shared pellet is credited once in declared collector order'
    terminal=replace(request,uid='terminal',world=replace(request.world,pellets=()))
    t=desk.inspect((terminal,)).transitions[0]
    assert t.actions==(None,None) and t.local_values==((),()) and t.after==terminal.world,'terminal inputs invent neither an action nor a local Q decision'
    assert candidate_distance(9,(1,7),(6,2))==10 and candidate_distance(9,(6,2),(1,7))==10 and candidate_distance(1,(0,0),(0,0))==0,'distance respects both axes, symmetry and stationary cells on the empty grid'
    requests=inspection_requests();expected=expected_inspection(requests)
    start=time.perf_counter();actual=desk.inspect(requests)
    assert actual==expected,'complete inspected Q rows, decisions, collection outcomes and joint states match independent expectations'
    elapsed=time.perf_counter()-start
    assert elapsed<0.08,'complete local-policy inspection stays within the declared local batch budget'

@pytest.mark.skip(reason="Part 2")
def test_part2_complete_binary_rollout(tmp_path):
    """Reopen complete ordered joint training and separate typed local records without conflating the two actors."""
    request=replace(example_request(),targets=((1,2),(4,3)));terminal=replace(request,uid='terminal',step=8,world=replace(request.world,pellets=()))
    report=GridDesk().inspect((request,terminal));special=replace(report.transitions[0],rewards=(-0.,0.))
    full=GridReport((special,*report.transitions,special));path=tmp_path/'all.bin';a=RolloutArchive(path);a.save(full);a.close()
    b=RolloutArchive(path);restored=b.reopen()
    assert restored==full,'binary snapshot retains all ordered equal transitions and complete joint/local fields'
    assert restored.transitions[0].observations[0]!=restored.transitions[0].observations[1] and restored.transitions[0].local_values[0]==special.local_values[0],'each declared actor retains its own observation and Q row'
    assert struct.pack('<d',restored.transitions[0].rewards[0])==struct.pack('<d',-0.),'binary64 reward sign survives close and reopen'
    assert restored.transitions[2].actions==(None,None) and restored.transitions[2].done,'terminal absence stays independent of central training-state presence'
    assert path.read_bytes().startswith(b'CTDE1') and restored.transitions[0].before==special.before and restored.transitions[0].policy=='scripted-local-Q-v1','durable binary training state is not a claim of trained policy'
    b.save(GridReport(()));b.close();c=RolloutArchive(path)
    assert c.reopen()==GridReport(()),'a complete empty snapshot replaces prior rollout contents'
    c.close()
    with pytest.raises(ValueError,match='closed archive'):c.reopen()
    fractional=replace(special,local_values=((replace(special.local_values[0][0],value=.125),replace(special.local_values[0][1],value=-0.),*special.local_values[0][2:]),special.local_values[1]))
    precision_path=tmp_path/'fractional.bin';precision=RolloutArchive(precision_path);precision.save(GridReport((fractional,)));precision.close()
    precision_reader=RolloutArchive(precision_path);precision_report=precision_reader.reopen();precision_reader.close()
    assert precision_report==GridReport((fractional,)) and tuple(struct.pack('<d',x.value)for x in precision_report.transitions[0].local_values[0][:2])==(struct.pack('<d',.125),struct.pack('<d',-0.)),'every declared finite local Q value retains its binary64 identity on archive reopen'

@pytest.mark.skip(reason="Part 3")
def test_part3_numeric_certificate_and_joint_value(tmp_path):
    """Implement actual numeric mixing, sufficient structural certificate and finite fixed-state Cartesian value comparison."""
    t=reopened_report(tmp_path,(example_request(),)).transitions[0];rows=t.local_values;features=training_features(t)
    spec=MixerSpec(((1.,2.),(.5,0.)),(-2.,1.),((.25,0.),(0.,.5)),('relu','identity'),(2.,1.),3.,(.5,-1.))
    q=tuple(max(x.value for x in row)for row in rows);size,step=features
    expected=3.+.5*size-step+2.*max(0.,-2.+q[0]+2.*q[1]+.25*size)+1.+.5*q[0]+.5*step
    assert mix_joint_value(spec,q,features)==expected,'hidden activations and fixed training features enter the declared numerical mixer'
    assert validate_monotonicity(spec)==Monotonicity(True,()),'nonnegative hidden and output weights certify this monotone architecture'
    oracle=joint_action_oracle(spec,rows,features)
    assert oracle.best_value==expected==oracle.greedy_value and oracle.value_gap==0. and oracle.combinations==25,'actual restored local Q rows feed all Cartesian joint values'
    r=((ActionValue('low',0.),ActionValue('high',2.)),(ActionValue('low',0.),ActionValue('high',1.)))
    output_negative=MixerSpec(((1.,1.),),(0.,),((0.,0.),),('identity',),(-1.,))
    assert validate_monotonicity(output_negative)==Monotonicity(False,('output[0]',)),'negative output coefficients also invalidate the sufficient structural certificate'
    negative=MixerSpec(((-1.,0.),),(0.,),((0.,0.),),('identity',),(1.,))
    assert validate_monotonicity(negative)==Monotonicity(False,('hidden[0][0]',)),'negative coefficient locations invalidate the sufficient structural certificate'
    bad=joint_action_oracle(negative,r,(0.,0.))
    assert bad.greedy_value==-2. and bad.best_value==0. and bad.value_gap==2. and bad.best_actions[0]=='low','a real counterexample reports the enumerated value gap rather than inferring one from a negative edge'
    cancellation=MixerSpec(((2.,0.),(-1.,0.)),(0.,0.),((0.,0.),(0.,0.)),('identity','identity'),(1.,1.))
    assert not validate_monotonicity(cancellation).certified and joint_action_oracle(cancellation,r,(0.,0.)).value_gap==0.,'a failed sufficient certificate need not create an actual greedy value gap'
    zero=MixerSpec(((1.,1.),),(0.,),((0.,0.),),('identity',),(0.,),7.)
    tied=joint_action_oracle(zero,r,(0.,0.))
    assert tied.greedy_value==tied.best_value==7. and tied.greedy_actions!=tied.best_actions,'zero weights permit different action tuples with equal optimal value'
    relu=MixerSpec(((1.,0.),),(-3.,),((0.,0.),),('relu',),(2.,),1.)
    assert mix_joint_value(relu,(2.,1.),(0.,0.))==1.,'hidden ReLU clips its own affine value before the output layer'
    with pytest.raises(ValueError,match='bounded finite local Q values'):mix_joint_value(relu,(float('nan'),1.),(0.,0.))
    late=reopened_report(tmp_path,(replace(example_request(),step=1001),)).transitions[0]
    assert training_features(late)==(7.,1001/1002) and joint_action_oracle(spec,late.local_values,training_features(late)).value_gap==0.,'large original joint steps retain their identity while bounded fixed training features remain integrable'


@pytest.mark.skip(reason="Part 4")
def test_part4_actual_joint_transition_csv():
    """Project one CSV row per joint turn with own local fields and explicitly permitted central training data."""
    request=replace(example_request(),targets=((1,2),(4,3)));terminal=replace(request,uid='end',step=8,world=replace(request.world,pellets=()))
    report=GridDesk().inspect((request,terminal))
    class Source:
        def __init__(self):self.it=iter(report.transitions);self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            try:return next(self.it)
            except StopIteration:raise StopAsyncIteration
        async def aclose(self):self.closed=True
    source=Source();handle=io.StringIO(newline='');writer=CSVWriter(handle);asyncio.run(serve(source,writer))
    reader=csv.DictReader(io.StringIO(handle.getvalue()));rows=list(reader)
    assert tuple(reader.fieldnames)==FIELDS and len(rows)==len(report.transitions)==2,'each actual simultaneous joint transition owns one ordered CSV row'
    for row,t in zip(rows,report.transitions):
        assert row['episode']==t.episode and int(row['step'])==t.step and row['policy']=='scripted-local-Q-v1','CSV identity and label belong to the actual scripted joint turn'
        for i in range(2):
            o=t.observations[i];s=str(i)
            assert json.loads(row['obs'+s])==[o.agent_uid,o.size,list(o.cell),list(o.target)] and json.loads(row['q'+s])==[[x.action,x.value]for x in t.local_values[i]],'each actor column carries its own typed local observation and Q values'
            assert json.loads(row['action'+s])==t.actions[i] and json.loads(row['reward'+s])==t.rewards[i],'per-agent action and actual reward are not replaced by joint summaries'
        assert json.loads(row['done'])==t.done and json.loads(row['training_state'])==[t.before.size,[list(x)for x in t.before.positions],[list(x)for x in t.before.pellets],[list(x)for x in t.after.positions],[list(x)for x in t.after.pellets]],'central training-only state remains a distinct explicit log column'
    assert source.closed and writer.closed and json.loads(rows[1]['action0'])is None,'publication closes resources and preserves a terminal missing action'

@pytest.mark.skip(reason="Part 5")
def test_part5_nested_numeric_path_certificates(tmp_path):
    """Evaluate real nested Sum/ReLU values and compose sufficient signed per-Q path certificates without claiming a universal counterexample."""
    request=replace(example_request(),targets=((5,5),(5,1)))
    t=reopened_report(tmp_path,(request,)).transitions[0]
    spec=MixerSpec(((1.,1.),),(0.,),((0.,0.),),('identity',),(1.,))
    oracle=joint_action_oracle(spec,t.local_values,training_features(t))
    q=tuple(next(x.value for x in row if x.action==a)for row,a in zip(t.local_values,oracle.greedy_actions));catalog=ExpressionCatalog(tuple(zip(('q0','q1'),q)))
    root=Sum('root',100.,(Weighted(2.,Sum('inner',1.,(Weighted(1.,QRef('r0','q0')),Weighted(3.,QRef('r1','q1'))))),Weighted(3.,Relu('clip',Sum('pre',2.,(Weighted(1.,QRef('r2','q0')),))))))
    audit=audit_expression(root,catalog)
    assert audit.value==100.+2.*(1.+q[0]+3.*q[1])+3.*max(0.,2.+q[0]) and audit.findings==(),'actual reopened local Q values feed every nested affine and ReLU node'
    assert audit.dependencies==(Dependency('q0',(2.,3.),True),Dependency('q1',(6.,),True)),'repeated local Q references retain each algebraic path contribution in declared Q order'
    assert audit.children[0].value==1.+q[0]+3.*q[1] and audit.children[1].children[0].value==2.+q[0],'every layer reports its own intermediate value before later activation'
    repeated=Sum('cancel',0.,(Weighted(2.,QRef('c0','q0')),Weighted(-1.,QRef('c1','q0'))))
    c=audit_expression(repeated,catalog)
    assert c.value==q[0] and c.dependencies==(Dependency('q0',(2.,-1.),False),),'a conservative negative-path certificate failure does not assert that the resulting function is nonmonotone'
    dead=audit_expression(Relu('dead',Sum('negative',0.,(Weighted(-1.,QRef('d','q')),))),ExpressionCatalog((('q',2.),)))
    assert dead.value==0. and not dead.dependencies[0].certified,'a dead ReLU may have zero realized value despite a failed sign certificate'
    masked=audit_expression(Sum('masked',9.,(Weighted(0.,Sum('negative-child',0.,(Weighted(-2.,QRef('z','q0')),))),)),catalog)
    assert masked.value==9. and masked.dependencies[0].certified,'a zero coefficient masks a downstream signed path without changing the constant bias'
    tiny=audit_expression(Sum('tiny-root',0.,(Weighted(-1e-162,Sum('tiny-child',0.,(Weighted(1e-162,QRef('tiny-q','q')),))),)),ExpressionCatalog((('q',1000.),)))
    assert tiny.value<0. and tiny.dependencies==(Dependency('q',(Fraction(-1e-162)*Fraction(1e-162),),False),),'a nonzero negative exact path cannot become a certified zero mask through binary64 underflow'

    missing=audit_expression(Sum('unknown-root',0.,(Weighted(1.,QRef('unknown-leaf','absent')),)),catalog)
    assert missing.value is None and missing.findings==(ExpressionFinding('unknown-Q',('unknown-root','unknown-leaf'),'absent'),),'unknown Q references name their actual nested context path'
    constant=audit_expression(Constant('constant',-4.),catalog)
    assert constant.value==-4. and constant.dependencies==() and constant.children==(),'constant global bias has no local Q dependency'
    declared_catalog=ExpressionCatalog((('z',2.),('a',3.)))
    declared_order=audit_expression(Sum('declared-order',0.,(Weighted(2.,QRef('a-leaf','a')),Weighted(1.,QRef('z-leaf','z')))),declared_catalog)
    assert declared_order.value==8. and declared_order.dependencies==(Dependency('z',(Fraction(1),),True),Dependency('a',(Fraction(2),),True)) and tuple(child.uid for child in declared_order.children)==('a-leaf','z-leaf'),'per-Q certificates retain declared catalog order independently of algebraic child order'
