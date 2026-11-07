"""Five locked local epistemic replay stages: visibility/control, durable history, three decisions, patches and bounded contexts."""
import json,time
from random import Random
from decimal import Decimal
from dataclasses import replace
import pytest
from mindtrace.models import *
from mindtrace.primitives import append_observation,deliver_visible_event,withdraw_completed_target,available_view
from mindtrace.support import ObservationLog,observation_view
from mindtrace.service import ReplayDesk
from mindtrace.store import BeliefArchive
from mindtrace.reasoning import build_other_models,predict_subject_target,choose_own_target
from mindtrace.stream import patch_operations
from mindtrace.wire_support import model_deltas,publish_patches,parse_patches,logical_path
from mindtrace.structure_support import EpistemicGraph,graph_from_predictions
from mindtrace.structure import resolve_belief_query
from mindtrace.fixture import replay_fixture

A=('team','Alice');B=('team','Bob');C=('team','Carol')
def sample():
    population=(Agent(A,'same'),Agent(B,'same'),Agent(C,'Carol'))
    old=Observation('old',BeliefKey(B,A,'target'),'unseen-old',0,0,'action')
    events=(VisibleEvent('approach',B,'target','ghost',1,2,'action',(A,)),VisibleEvent('late',B,'target','future',3,0,'action',(A,)))
    return ReplayRequest(population,events,(old,),(Target(B,'ghost'),Target(C,'blue')),(C,),World('world',0,frozenset(('blue','green'))),17,1)

def reopened(tmp_path):
    request=sample();report=ReplayDesk().run(request)
    priors=(SubjectPrior(B,('old','phantom'),('old',)),SubjectPrior(C,('green',),('green',)))
    snapshot=EpistemicSnapshot('episode',request.population,report.observations,(BeliefVersion('b1',BeliefKey(A,B,'target'),'phantom',0,0,'old'),),priors)
    archive=BeliefArchive(tmp_path/'belief.sqlite');archive.save(snapshot);archive.close();archive=BeliefArchive(tmp_path/'belief.sqlite');restored=archive.load();archive.close()
    models=build_other_models(restored,A,1,report.request.completed);predictions=tuple(predict_subject_target(m)for m in models)
    return report,restored,models,predictions

@pytest.mark.skip('Part 1')
def test_visible_writer_completion_and_complete_joint_control():
    """Repair actual observer/subject writes, explicit witness delivery and completed intentions, then preserve a complete same-generation joint control report within its local budget."""
    request=sample();actual=ReplayDesk().run(request)
    assert actual.receipts[0].visible_records[0].key==BeliefKey(A,B,'target') and actual.receipts[0].visible_records[0].value=='ghost','the correct requested observer subject key reaches the natural evidence consumer'
    assert tuple(o.key.observer for o in actual.receipts[0].delivered)==(A,) and actual.observations[0]==request.initial_observations[0] and len(actual.receipts)==1,'only declared witnesses receive current events and unseen prior evidence stays intact'
    assert withdraw_completed_target(request.active_targets,(C,))==(Target(B,'ghost'),) and actual.observations[0].uid=='old','completion withdraws only active intentions without deleting historical observations'
    query,expected=replay_fixture();started=time.perf_counter();observed=ReplayDesk().run(query)
    assert observed==expected,'the complete actual observation joint choices RNG settlement duplicates inventory and final replay report stay exact'
    elapsed=time.perf_counter()-started
    assert elapsed<0.04,'complete supplied epistemic replay respects its local response budget'
    cache={};view=available_view(request.world,cache)
    assert available_view(request.world,cache)==view and view.boxes==('blue','green'),'all joint-turn control choices retain the same canonical immutable actual inventory'
    changed=World('world',1,frozenset(('green',)));peer=World('other',0,frozenset(('red',)))
    assert available_view(changed,cache).boxes==('green',) and available_view(peer,cache).boxes==('red',) and view.boxes==('blue','green'),'generation and world identity bind independent actual control views without a private prediction filter'
    empty=ReplayDesk().run(replace(request,events=(),world=World('empty',0,frozenset()),completed=()))
    assert empty.control.choices==empty.control.taken==() and empty.control.world.generation==0 and empty.control.random_state==Random(17).getstate(),'empty actual inventories perform no random draw or invented collection'
    two=ObservationLog();event=replace(request.events[0],visible_to=(C,A));rows=deliver_visible_event(two,event,request.population)
    assert tuple(r.key.observer for r in rows)==(A,C) and len(two.rows)==2,'witness evidence follows declared population order rather than witness tuple order'

@pytest.mark.skip('Part 2')
def test_complete_observation_and_independent_belief_history_sqlite(tmp_path):
    """Reopen full typed observation and believed-version rows with own identities, source links and declaration order."""
    q=sample();key=BeliefKey(A,B,'target');obs=(Observation('o2',key,'same',2**60+2,2,'fact'),Observation('o1',key,'same',2**60+1,1,'action'),Observation('other',BeliefKey(B,A,'target'),False,0,0,'fact'))
    beliefs=(BeliefVersion('v2',key,('believed',Decimal('1.00000000000000000001')),4,2,'o2'),BeliefVersion('v1',key,None,3,1,None),BeliefVersion('v3',BeliefKey(C,B,'target'),False,0,0,'other'))
    expected=EpistemicSnapshot('history',tuple(reversed(q.population)),obs,beliefs,(SubjectPrior(B,('ghost','blue'),('ghost',)),));archive=BeliefArchive(tmp_path/'state.sqlite');archive.save(expected);archive.close();archive=BeliefArchive(tmp_path/'state.sqlite');actual=archive.load();archive.close()
    assert actual==expected,'every ordered observation independent believed version and snapshot field reopens exactly'
    assert tuple(x.uid for x in actual.observations)==('o2','o1','other') and tuple(x.uid for x in actual.beliefs)==('v2','v1','v3'),'same-key and repeated-value histories keep every independent domain row in declaration order'
    assert actual.observations[0].key==key and actual.observations[2].key==BeliefKey(B,A,'target') and actual.beliefs[0].source_uid=='o2','each observation and belief version retains its own subject observer proposition and evidence association'
    assert actual.beliefs[0].value==beliefs[0].value and actual.beliefs[1].value is None and actual.beliefs[2].value is False,'the complete supplied scalar codec preserves independent beliefs rather than substituting observed truth'
    assert actual.population[1].name==actual.population[2].name and actual.priors==expected.priors and actual.observations[0].turn==2**60+2,'display names do not replace declared identity priors or exact domain clocks'
    replacement=replace(expected,uid='empty',observations=(),beliefs=(),priors=());archive=BeliefArchive(tmp_path/'state.sqlite');archive.save(replacement);archive.close();archive=BeliefArchive(tmp_path/'state.sqlite')
    assert archive.load()==replacement,'a complete snapshot replacement does not retain previous observation or belief rows'
    archive.close()

    completed_snapshot=replace(expected,uid='completed-history',population=(replace(expected.population[0],collected=True),)+expected.population[1:])
    archive=BeliefArchive(tmp_path/'state.sqlite');archive.save(completed_snapshot);archive.close();archive=BeliefArchive(tmp_path/'state.sqlite');completed_reopened=archive.load();archive.close()
    assert completed_reopened==completed_snapshot and completed_reopened.population[0].collected is True,'reopening preserves each agent completed status beside its independent epistemic histories'

@pytest.mark.skip('Part 3')
def test_interpret_other_models_predict_perceived_domain_and_choose_actual(tmp_path):
    """Interpret real reopened visible actions, predict each subject's perceived choice, then choose only from own real inventory with the declared RNG contract."""
    report,snapshot,models,predictions=reopened(tmp_path)
    assert models[0]==SubjectModel(B,('old','phantom','ghost'),('ghost','old'),True,1,('approach:["team", "Alice"]',)),'actual reopened visible approach evidence updates that subject prior while preserving perceived alternatives'
    assert models[1].active is False and models[1].preference==('green',) and models[1].source_ids==(),'each subject keeps independent prior state and supplied completion activity'
    assert predictions==(Prediction(B,'ghost',models[0].source_ids),Prediction(C,None,())) and 'ghost'not in report.control.view.boxes,'a subject prediction uses its own perceived domain even when the actual world has no such token'
    all_observations=(Observation('later',BeliefKey(A,B,'target'),'new',2,0,'action'),Observation('first',BeliefKey(A,B,'target'),'old',1,0,'action'),Observation('invisible',BeliefKey(C,B,'target'),'wrong',3,0,'action'),Observation('future',BeliefKey(A,B,'target'),'future',5,0,'action'))
    ordered=build_other_models(replace(snapshot,observations=all_observations),A,2,())
    assert ordered[0].preference==('new','old') and ordered[0].believed_available==('old','phantom','new') and ordered[0].source_ids==('first','later') and ordered[0].last_seen_turn==2,'interpretation follows actual visible action time order without dropping older alternative beliefs'
    unavailable=SubjectModel(B,('phantom','ghost'),('real','ghost'),True,None,())
    assert predict_subject_target(unavailable).target=='ghost' and predict_subject_target(replace(unavailable,preference=('real',))).target=='phantom','subject preference falls back within that subject perceived candidates rather than the actual world'
    view=AvailableView('actual',2,('blue','green','red'));rng=Random(73);expected_rng=Random(73);actual=choose_own_target(view,(Prediction(B,'blue',()),Prediction(C,'ghost',())),rng)
    assert actual==expected_rng.choice(('green','red')) and rng.getstate()==expected_rng.getstate(),'own exclusion uses actual candidates and consumes exactly one declared random choice'
    rng=Random(9);expected_rng=Random(9);full=tuple(Prediction((str(i),),b,())for i,b in enumerate(view.boxes))
    assert choose_own_target(view,full,rng)==expected_rng.choice(view.boxes) and rng.getstate()==expected_rng.getstate(),'when other predictions cover the whole inventory own fallback stays in that same real inventory'
    rng=Random(5);state=rng.getstate()
    assert choose_own_target(replace(view,boxes=()),predictions,rng) is None and rng.getstate()==state,'no actual token returns no choice without consuming RNG or falling back to a false belief'
    assert predict_subject_target(replace(unavailable,active=False)).target is None and predict_subject_target(replace(unavailable,believed_available=())).target is None,'inactive and perceived-empty subjects have explicit typed no-target predictions'

@pytest.mark.skip('Part 4')
def test_ordered_observer_local_actual_json_patch_projection(tmp_path):
    """Project each actual admitted delta's own operation, complete logical path and value through the supplied complete Patch lifecycle."""
    _,_,_,predictions=reopened(tmp_path);derived=model_deltas(A,predictions,1);key=BeliefKey(A,('agent/a~b',),'p/~')
    deltas=derived+(ModelDelta(key,'replace',False,2,'false'),ModelDelta(key,'replace',None,3,'null'),ModelDelta(key,'remove','ignored',4,'remove'),ModelDelta(BeliefKey(C,B,'target'),'replace','private',2,'peer'),ModelDelta(key,'replace','future',9,'future'))
    class Source:
        def __init__(self,rows):self.rows=rows;self.closed=False
        def __iter__(self):return iter(self.rows)
        def close(self):self.closed=True
    source=Source((PatchBatch(A,4,deltas),PatchBatch(A,0,())));texts=publish_patches(source,patch_operations);rows=tuple(parse_patches(t)for t in texts)
    assert source.closed and len(rows)==2 and rows[1]==[],'complete publication retains empty patch documents and closes the supplied source'
    assert rows[0][:2]==[{'op':'replace','path':logical_path(d.key),'value':d.value}for d in derived],'actual candidate predictions flow into their own observer subject patch fields'
    assert tuple(r['op']for r in rows[0])==('replace','replace','replace','replace','remove') and len(rows[0])==5,'every admitted repeated-path operation remains in actual declaration order'
    assert rows[0][2]['value'] is False and rows[0][3]['value'] is None and set(rows[0][4])=={'op','path'},'own values and supplied explicit remove classification retain their operation-specific fields'
    assert rows[0][2]['path']==rows[0][3]['path']==rows[0][4]['path']==logical_path(key) and '~1'in rows[0][2]['path'] and '~0'in rows[0][2]['path'],'each actual delta projects its own complete supplied logical path without reusing a prior record path'
    assert all('private'not in str(row) and 'future'not in str(row)for row in rows[0]),'the complete supplied observer and time admission boundary reaches the actual projection'

@pytest.mark.skip('Part 5')
def test_finite_higher_order_current_context_interpreter(tmp_path):
    """Walk bounded requested subject chains through successive current model nodes, preserving context and exact known or unknown results."""
    _,_,_,predictions=reopened(tmp_path);base=graph_from_predictions(A,predictions)
    graph=EpistemicGraph(tuple(replace(n,children=((C,'bob-about-carol'),))if n.uid=='subject-model:0'else n for n in base.nodes.values())+(EpistemicNode('bob-about-carol',C,(('target','other-ghost'),('truthy',False),('known-null',None)),((B,'carol-about-bob'),)),EpistemicNode('carol-about-bob',B,(('target','deeper'),),((C,'bob-about-carol'),))))
    first=resolve_belief_query(graph,BeliefQuery('observer-root',(B,),'predicted-target',4));second=resolve_belief_query(graph,BeliefQuery('observer-root',(B,C),'target',4))
    assert first.value==predictions[0].target=='ghost' and first.contexts==('observer-root','subject-model:0'),'actual reopened P3 prediction becomes the first-order model evidence consumed by the interpreter'
    assert second==BeliefAnswer('known','other-ghost',('observer-root','subject-model:0','bob-about-carol'),2,2),'a second-order answer comes from the actual successive subject context rather than the root or first order'
    deeper=resolve_belief_query(graph,BeliefQuery('observer-root',(B,C,B),'target',4))
    assert deeper.value=='deeper' and deeper.contexts[-1]=='carol-about-bob' and deeper.traversed_order==3,'the same agent in different contexts keeps its distinct actual nested beliefs'
    cyclic=resolve_belief_query(graph,BeliefQuery('observer-root',(B,C,B,C),'target',4))
    assert cyclic.value=='other-ghost' and cyclic.contexts==('observer-root','subject-model:0','bob-about-carol','carol-about-bob','bob-about-carol'),'finite requested cycles revisit a model without a global agent or node visited cutoff'
    missing=resolve_belief_query(graph,BeliefQuery('observer-root',(B,A),'target',4))
    assert missing==BeliefAnswer('unknown',None,('observer-root','subject-model:0'),2,1),'a missing link returns the supplied typed unknown at its actual traversed context without root or world fallback'
    assert resolve_belief_query(graph,BeliefQuery('observer-root',(B,C),'truthy',4)).value is False and resolve_belief_query(graph,BeliefQuery('observer-root',(B,C),'known-null',4)).status=='known','complete supplied answer construction preserves known false and known null independently of missing belief'
    root=EpistemicGraph((EpistemicNode('root',A,(('target','own'),)),))
    assert resolve_belief_query(root,BeliefQuery('root',(),'target',0))==BeliefAnswer('known','own',('root',),0,0),'an empty requested chain reads the root itself at order zero'
