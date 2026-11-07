"""Five locked stages: PSO numeric replay, full checkpoint, delayed ACO policy, NDJSON and nested ant trails."""
import math
import struct
from dataclasses import replace
from random import Random
from time import perf_counter
import pytest
from swarmtune.models import *
from swarmtune.primitives import update_personal_best,step_particle,update_global_best
from swarmtune.scoring import best_report,source_fitness
from swarmtune.service import OptimizationDesk,outcome_from_report
from swarmtune.fixture import initial_state,optimization_fixture
from swarmtune.store import OptimizerArchive
from swarmtune.routing_support import stable_snapshot
from swarmtune.routing import choose_task_route,apply_route_decay,apply_verified_feedback
from swarmtune.stream import observation_fields
from swarmtune.wire_support import publish_observations,parse_observations
from swarmtune.graph_support import GraphCatalog
from swarmtune.structure import audit_expeditions

@pytest.mark.skip("Part 1")
def test_part1_numeric_optimizer_replay():
    """Restore flat numeric best ownership, actual bounds, maximizing best and changed-score work in a full optimizer replay."""
    bounds=((0.,1.),(0.,1.));p=Particle('one',[.72,.4],[.2,.2],[0.,0.],0.);score=source_fitness(p.x,bounds)
    update_personal_best(p,score);step_particle(p,Best((.72,.4),score),bounds,1.,0.,0.,.2,.3);view=best_report(p,bounds)
    assert view.p_best==(.72,.4)and view.p_best_fit==score,'personal best retains its own improved coordinates after later actual motion'
    p.x[0]=.1
    assert view.x==(.72+.2,.4+.2)and p.p_best==[.72,.4],'numeric receipts and personal best remain separate flat value vectors'
    qscore=source_fitness((.9,.1),bounds);q=Particle('boundary',[.9,.1],[.8,-.8],[.9,.1],qscore);step_particle(q,Best((.9,.1),qscore),bounds,1.,0.,0.,.2,.3)
    assert source_fitness(q.x,bounds)>=0 and q.x==[1.,0.]and q.v==[.8,-.8],'actual coordinates respect bounds without clipping the declared velocity'
    lo=Best((0.,0.),0.);q.x=[.72,.4];better=update_global_best(lo,q,score)
    assert better==Best((.72,.4),score),'best-so-far maximizes the actual evaluator rather than accepting a worse score'
    left=(.72-.1,.4);right=(.72+.1,.4);tied=Best(left,source_fitness(left,bounds));q.x=list(right)
    assert update_global_best(tied,q,source_fitness(q.x,bounds))==tied,'equal evaluator values retain the previously declared maximizing best'
    job,expected=optimization_fixture();desk=OptimizationDesk();start=perf_counter();actual=desk.run(job)
    assert actual==expected,'full changed steps, iteration vectors, numeric summaries, own bests, final RNG and allocation match independent replay'
    elapsed=perf_counter()-start
    assert elapsed<.16,f'full numeric optimizer replay exceeds the declared work budget: {elapsed:.9f}'
    records=desk.evaluator.trace;n=len(job.state.particles);needed=n*(1+job.iterations)
    evidence=set(records)
    assert len(records)>=needed and all((('changed',r.iteration,i%n),r.particle_uid,r.x,r.fitness)in evidence for i,r in enumerate(actual.changed_steps)),'every real changed candidate is evaluated with its actual coordinates and score'
    zero,zero_expected=optimization_fixture(3,0)
    assert OptimizationDesk().run(zero)==zero_expected,'a declared zero-iteration numeric job retains its complete initialized checkpoint'
    assert actual.state.iteration==job.iterations and len(actual.iterations)==job.iterations and actual.state.best.fitness>=job.state.best.fitness,'all declared iterations complete with a nondecreasing actual best'

@pytest.mark.skip("Part 2")
def test_part2_binary_checkpoint_and_deferred_outcomes(tmp_path):
    """Store all numeric/RNG fields and independent route, allocation and deferred-arrival records, then resume an actual job."""
    job,_=optimization_fixture(4,2);report=OptimizationDesk().run(job);outcome=outcome_from_report(report,'feedback-1',91,4)
    table=RouteTable((RouteRow('text',(('writer',3.),('critic',1.))),RouteRow('math',(('numeric-agent',2.),('other',5.)))),(1,3))
    second=Outcome('feedback-2','other-allocation',.6,False,True,12,7);allocations=(job.allocation,Allocation('other-allocation','other-job','text','critic'))
    checkpoint=ExperimentCheckpoint('checkpoint-19',report.state,table,allocations,(outcome,second));archive=OptimizerArchive(tmp_path/'binary');archive.save(checkpoint);archive.close();reopened=OptimizerArchive(tmp_path/'binary');loaded=reopened.load();reopened.close()
    assert loaded==checkpoint,'binary checkpoint retains every numeric vector, RNG value, routing row, ledger and pending outcome'
    continued=OptimizationDesk().run(replace(job,state=loaded.state,iterations=2));expected=OptimizationDesk().run(replace(job,iterations=4))
    assert continued.state==expected.state,'reopened optimizer continues the exact Random state and numeric best rather than restarting a seed'
    special=replace(loaded.state,particles=(ParticleState('bits',(-0.,5e-324),(1e-300,-0.),(.72,.4),.84),),best=Best((.72,.4),.84));bits=replace(checkpoint,uid='bits',state=special,pending=(second,outcome,second))
    archive=OptimizerArchive(tmp_path/'bits');archive.save(bits);archive.close();again=OptimizerArchive(tmp_path/'bits');decoded=again.load();again.close()
    assert struct.pack('>4d',*decoded.state.particles[0].x,*decoded.state.particles[0].v)==struct.pack('>4d',-0.,5e-324,1e-300,-0.),'complete Given binary codec preserves the declared binary64 vector bits'
    assert decoded.state==special,'all independent current velocity own-best and global-best numeric members reopen without substitution'
    assert decoded.pending==(second,outcome,second)and decoded.allocations==allocations and decoded.table==table,'independent arrival order and repeated outcome records are retained as declared'
    assert (tmp_path/'binary'/'state.bin').read_bytes().startswith(b'SW19\x01')and (tmp_path/'binary'/'metadata.json').is_file(),'numeric vectors and full domain metadata use their declared separate checkpoint members'

@pytest.mark.skip("Part 3")
def test_part3_task_roulette_epoch_decay_and_verified_feedback(tmp_path):
    """Implement requested-row roulette, once-per-epoch numeric decay and original-allocation delayed learning as three independent algorithms."""
    class Draw:
        def __init__(self,value):self.value=value;self.calls=0
        def random(self):self.calls+=1;return self.value
    table=RouteTable((RouteRow('text',(('silent',0.),('writer',1.),('critic',3.))),RouteRow('math',(('numeric-agent',2.),('other',2.)))))
    rng=Draw(.25);snapshot=stable_snapshot(table);choice=choose_task_route(snapshot,'text-next','text',rng)
    assert choice.agent_uid=='critic'and choice.draw==1. and choice.total==4. and rng.calls==1 and choice.snapshot==snapshot,'requested row uses one real draw and half-open weighted intervals in declared order'
    math_choice=choose_task_route(snapshot,'math-now','math',Draw(.75))
    assert math_choice.agent_uid=='other'and math_choice.task_type=='math'and math_choice.draw==3.,'weighted selection binds the requested task row independently of the first declared row'
    with pytest.raises(ValueError,match='positive-total'):
        choose_task_route(RouteTable((RouteRow('huge',(('a',1e308),('b',1e308))),)),'overflow','huge',Draw(.5))
    edge=choose_task_route(snapshot,'zero-boundary','text',Draw(0.))
    assert edge.agent_uid=='writer'and table==snapshot,'zero weight has no interval and inference does not mutate routing weights'
    decayed=apply_route_decay(table,9,.5,.75)
    assert decayed==RouteTable((RouteRow('text',(('silent',.75),('writer',.75),('critic',1.5))),RouteRow('math',(('numeric-agent',1.),('other',1.)))),(9,)),'explicit decay updates every actual row with the declared floor and order'
    assert apply_route_decay(decayed,9,.5,.75)==decayed and apply_route_decay(decayed,10,0.).applied_epochs==(9,10),'a replayed epoch is not applied twice and a distinct epoch remains explicit'
    job,_=optimization_fixture(3,1);report=OptimizationDesk().run(job);real=outcome_from_report(report,'real-outcome',44,9);allocations=(job.allocation,Allocation('unrelated','text-later','text','critic'));checkpoint=ExperimentCheckpoint('integrated',report.state,table,allocations,(real,));archive=OptimizerArchive(tmp_path/'feedback');archive.save(checkpoint);archive.close();archive=OptimizerArchive(tmp_path/'feedback');restored=archive.load();archive.close();policy=LearningPolicy(0.,.25);learned=apply_verified_feedback(restored.table,restored.allocations,restored.pending[0],policy)
    assert learned.decision.accepted and learned.decision.task_uid==job.allocation.task_uid and learned.decision.agent_uid=='numeric-agent'and learned.table.rows[0]==table.rows[0],'actual reopened numeric feedback rewards its original allocation rather than the current inference task'
    assert learned.table.rows[1].weights==(('numeric-agent',2.+.25*real.quality),('other',2.))and learned.decision.amount==.25*real.quality,'accepted learning adds only the actual original task-agent amount'
    boundary=apply_verified_feedback(table,allocations,replace(real,quality=.6),LearningPolicy(.6,.2))
    assert boundary.decision.accepted and boundary.decision.amount==.12,'the disclosed quality threshold is inclusive'
    with pytest.raises(ValueError,match='representable learning'):
        apply_verified_feedback(RouteTable((RouteRow('math',(('numeric-agent',1e308),)),)),allocations,replace(real,quality=1.),LearningPolicy(0.,1e308))
    rejected=tuple(apply_verified_feedback(table,allocations,o,LearningPolicy(.6,.2))for o in(replace(real,verified=False),replace(real,success=False),replace(real,quality=.59),replace(real,allocation_uid='missing')))
    assert tuple(r.decision.reason for r in rejected)==('unverified','failed','below-quality','unknown-allocation')and all(r.table==table and not r.decision.accepted and r.decision.amount==0. for r in rejected),'rejected actual outcomes retain their own reason without adding any route or reinforcement'

@pytest.mark.skip("Part 4")
def test_part4_actual_iteration_route_and_learning_ndjson(tmp_path):
    """Project each actual observation's own numeric/inference/learning fields; classification and NDJSON lifecycle are complete Given."""
    job,_=optimization_fixture(3,2);report=OptimizationDesk().run(job);table=RouteTable((RouteRow('math',(('numeric-agent',1.),('other',1.))),));outcome=outcome_from_report(report,'observed',15,6);archive=OptimizerArchive(tmp_path/'wire');archive.save(ExperimentCheckpoint('wire',report.state,table,(job.allocation,),(outcome,)));archive.close();archive=OptimizerArchive(tmp_path/'wire');restored=archive.load();archive.close();choice=choose_task_route(stable_snapshot(restored.table),'inference-now','math',Random(3));yes=apply_verified_feedback(restored.table,restored.allocations,outcome,LearningPolicy(0.,.2)).decision;no=apply_verified_feedback(restored.table,restored.allocations,replace(outcome,uid='rejected',verified=False),LearningPolicy(0.,.2)).decision
    class Source:
        def __init__(self,events):self.events=events;self.closed=False
        def __iter__(self):return iter(self.events)
        def close(self):self.closed=True
    source=Source((IterationObservation('run-own',report.iterations[0]),RouteObservation(choice),LearningObservation(yes),IterationObservation('run-own',report.iterations[1]),LearningObservation(no)));wire=publish_observations(source,observation_fields);rows=parse_observations(wire)
    assert source.closed and len(rows)==5 and tuple(r['kind']for r in rows)==('iteration','route','learning','iteration','learning'),'every actual typed observation is published in source order and the complete driver closes its source'
    assert rows[0]==dict(kind='iteration',run='run-own',iteration=1,best_fitness=report.iterations[0].best.fitness,mean_fitness=report.iterations[0].population_mean,best=list(report.iterations[0].best.coordinates),current_scores=list(report.iterations[0].current_scores)),'iteration projection retains its own actual best, distinct mean and full current score vector'
    assert rows[1]==dict(kind='route',task='inference-now',task_type='math',agent=choice.agent_uid,draw=choice.draw,total=choice.total),'inference projection uses its own actual choice without inventing a learning amount'
    assert rows[2]==dict(kind='learning',outcome='observed',allocation=job.allocation.uid,task=job.allocation.task_uid,task_type='math',agent='numeric-agent',arrival=15,epoch=6,quality=yes.quality,status='accepted',amount=yes.amount,reason='accepted'),'learning projection retains original task attribution and actual arrival, epoch and sealed numeric amount'
    assert rows[3]['iteration']==2 and rows[3]['current_scores']==list(report.iterations[1].current_scores)and rows[4]['status']=='rejected'and rows[4]['amount']==0. and rows[4]['reason']=='unverified','later observations retain their own iteration and rejected decision rather than a cached earlier event'

@pytest.mark.skip("Part 5")
def test_part5_nested_ant_paths_and_shared_epoch_trails(tmp_path):
    """Build nested continuity/destination audits and actual visited-edge credit with multiplicity and shared epoch state; P3 quality decisions are Given dependencies."""
    table=RouteTable((RouteRow('math',(('numeric-agent',1.),)),));reports=[];outcomes=[];allocations=[]
    for i in range(5):
        seed=initial_state(3,40+i);anchor=ParticleState('p0',(.72,.4),(0.,0.),(.72,.4),source_fitness((.72,.4),seed.bounds));particles=(anchor,)+seed.particles[1:];top=max(particles,key=lambda p:p.p_best_fit);seed=replace(seed,particles=particles,best=Best(top.p_best,top.p_best_fit))
        job=OptimizationJob(Allocation('a'+str(i),'task'+str(i),'math','numeric-agent'),seed,1);report=OptimizationDesk().run(job);reports.append(report);allocations.append(job.allocation);outcomes.append(outcome_from_report(report,'o'+str(i),20-i,3 if i<3 else 4,verified=i!=4))
    archive=OptimizerArchive(tmp_path/'graph');archive.save(ExperimentCheckpoint('nested',reports[-1].state,table,tuple(allocations),tuple(outcomes)));archive.close();archive=OptimizerArchive(tmp_path/'graph');restored=archive.load();archive.close();decisions=tuple(apply_verified_feedback(restored.table,restored.allocations,o,LearningPolicy(0.,.2)).decision for o in restored.pending)
    edges=(Edge('ab','A','B'),Edge('ba','B','A'),Edge('bc','B','C'));catalog=GraphCatalog(edges,decisions);paths=(AntPath('loop','A','C',('ab','ba','ab','bc'),'o0',3),AntPath('broken','A','C',('bc',),'o1',3),AntPath('child','A','C',('ab','bc'),'o2',3),AntPath('short','A','C',('ab',),'o3',4),AntPath('rejected','A','C',('ab','bc'),'o4',4));roots=(Expedition('root',paths[:2],(Expedition('child-group',(paths[2],)),Expedition('late-group',(paths[3],)))),Expedition('other-root',(paths[4],)));state=TrailState(tuple(Trail(task,dest,e.uid,1.)for task,dest in(('math','C'),('math','D'),('other','C'))for e in edges));result=audit_expeditions(roots,catalog,state,.5)
    root,other=result.reports
    assert decisions[0].amount>0. and decisions[2].amount>0.,'actual numeric jobs provide nonzero sealed credit for the repeated-traversal and child path guards'
    assert root.before==state and other.before==root.after and other.after==result.state,'each root certificate exposes its actual before and after shared trail states'
    assert root.children[1].before==root.children[0].after and root.after==root.children[1].after,'nested certificates thread the actual prior child state through later children and their parent'
    assert root.own==(PathAudit('loop','deposited',('ab','ba','ab','bc'),decisions[0].amount),PathAudit('broken','discontinuous',(),0.)),'own finite paths retain every real edge traversal and reject discontinuous movement without deposit'
    assert root.children[0].own==(PathAudit('child','deposited',('ab','bc'),decisions[2].amount),)and root.children[1].own==(PathAudit('short','wrong-destination',('ab',),0.),),'nested reports preserve their own path destination failures and successful child evidence'
    assert other.own==(PathAudit('rejected','rejected-learning',('ab','bc'),0.),)and result.state.applied_epochs==(3,4),'all roots and children share epoch state while consuming the actual sealed P3 rejection'
    weights={(t.task_type,t.destination,t.edge_uid):t.weight for t in result.state.trails};a=decisions[0].amount;b=decisions[2].amount
    assert math.isclose(weights['math','C','ab'],(.5+2*a+b)*.5,rel_tol=0.,abs_tol=1e-15)and math.isclose(weights['math','C','ba'],(.5+a)*.5,rel_tol=0.,abs_tol=1e-15)and math.isclose(weights['math','C','bc'],(.5+a+b)*.5,rel_tol=0.,abs_tol=1e-15),'valid actual deposits preserve per-traversal multiplicity and decay each explicit epoch once across the nested forest'
    assert all(t.weight==.25 for t in result.state.trails if(t.task_type,t.destination)!=('math','C'))and state.applied_epochs==(),'unvisited task and destination trails receive decay but no foreign credit and the input snapshot remains unchanged'
    with pytest.raises(ValueError,match='representable graph'):
        audit_expeditions(roots,GraphCatalog(edges,(replace(decisions[0],amount=1e308),)+decisions[1:]),state,.5)
    rejected_first=audit_expeditions((Expedition('rejected-first',(paths[4],)),),catalog,state,.5)
    expected_rejected_state=TrailState(tuple(replace(t,weight=.5)for t in state.trails),(4,))
    assert rejected_first.state==expected_rejected_state and rejected_first.reports[0].before==state and rejected_first.reports[0].after==expected_rejected_state and rejected_first.reports[0].own==(PathAudit('rejected','rejected-learning',('ab','bc'),0.),),'a rejected first path still applies its new epoch decay before returning a complete path audit'
