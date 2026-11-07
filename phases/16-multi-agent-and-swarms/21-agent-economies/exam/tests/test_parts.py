"""Five locked parts: supplied statements, durable accounting, allocation algorithms, CSV and nested team games."""
import asyncio,csv,io,time
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction as F
from random import Random
import pytest
from creditecon.models import *
from creditecon.primitives import efficiency_report,second_price_payment,update_reputation,CoalitionOracle
from creditecon.game_support import UtilityEvaluator
from creditecon.service import CreditDesk
from creditecon.fixture import workload,expected_replay
from creditecon.store import AccountingArchive
from creditecon.allocation import shapley_exact,shapley_sampled,allocation_report
from creditecon.stream import export_blocks
from creditecon.team_support import TeamCatalog
from creditecon.structure import audit_teams

def simple_game():
    return Game('market,α',('a','b','null'),F(7),(Criterion('a-only',frozenset({'a'}),F(2)),Criterion('b-loss',frozenset({'b'}),F(-1))))
def snapshot():
    game=simple_game();desk=CreditDesk(game);alloc=(('a',F(2)),('b',F(-1)),('null',F(0)))
    replay=desk.replay((frozenset(),frozenset({'a'}),frozenset({'b'}),frozenset({'a'})))
    receipts=(QualityReceipt('unconfirmed','a',F(1),False,F(0)),QualityReceipt('confirmed','b',F(9,10),True,F(1,5)))
    return AccountingSnapshot(game,replay,(('a','b','null'),('null','b','a')),receipts,alloc,desk.statement(alloc),'unit,α',Decimal('0.0100'))
def reopen_snapshot(tmp_path,full=None):
    full=snapshot()if full is None else full;path=tmp_path/'account.sqlite';a=AccountingArchive(path);a.save(full);a.close();b=AccountingArchive(path);restored=b.load();b.close();return restored

@pytest.mark.skip(reason="Part 1")
def test_part1_supplied_credit_and_utility_replay():
    """Repair supplied surplus publication, second-price charge, confirmed EMA and complete game-scoped utility replay."""
    game=simple_game();desk=CreditDesk(game);credits=(('a',F(2)),('b',F(-1)),('null',F(0)))
    statement=desk.statement(credits)
    assert statement==Efficiency(game.uid,F(7),F(8),F(1),F(1),F(0)),'balanced supplied credits use the declared grand-minus-empty surplus'
    bids=(Bid('first',F(9)),Bid('second',F(4)),Bid('third',F(2)))
    assert second_price_payment(bids)==Payment('first',F(4)),'the first highest bidder pays the second-highest declared amount'
    pending=QualityReceipt('pending','a',F(1),False,F(0));confirmed=replace(pending,uid='checked',confirmed=True,quality=F(1,5))
    assert update_reputation(F(4,5),pending)==F(4,5),'an unconfirmed quality report does not change reputation'
    assert update_reputation(F(4,5),confirmed)==F(1,2),'confirmed quality rather than the optimistic self-report enters the EMA'
    assert second_price_payment((Bid('early',F(3)),Bid('late',F(3))))==Payment('early',F(3)) and second_price_payment((Bid('alone',F(9)),))is None,'stable auction ties and the no-sale domain remain explicit'
    assert update_reputation(F(0),replace(confirmed,quality=F(0)))==F(1,10),'the declared reputation floor remains active after confirmation'
    changed=replace(game,uid='other-market',baseline=F(-9));other=CreditDesk(changed)
    assert other.oracle.value({'null'}).value==F(-9) and desk.oracle.value({'null'}).value==F(7),'each immutable game owns its own coalition value domain'
    zero=CreditDesk(Game('zero',('z',),F(0),()));negative=CreditDesk(Game('negative',('z',),F(-3),()))
    assert zero.oracle.value({'z'}).value==F(0) and negative.oracle.value({'z'}).value==F(-3) and zero.oracle.value(('z','z')).coalition==frozenset({'z'}),'zero negative and repeated-member requests retain exact set-valued utility semantics'
    same_uid=CreditDesk(replace(game,baseline=F(-17),criteria=(Criterion('changed',frozenset({'a'}),F(41)),)))
    assert same_uid.oracle.value({'a'}).value==24 and desk.oracle.value({'a'}).value==9,'a new immutable game binding cannot borrow another instance value merely because its external UID matches'
    loss=Game('loss',('a',),F(5),(Criterion('loss',frozenset({'a'}),F(-2)),))
    assert CreditDesk(loss).statement((('a',F(-2)),)).surplus==F(-2),'a legitimate negative coalition surplus remains a signed balanced allocation'
    game,requests=workload();expected=expected_replay(game,requests);large=CreditDesk(game)
    start=time.perf_counter();actual=large.replay(requests)
    assert actual==expected,'complete ordered utility observations criterion contributions and totals match independent game expectations'
    elapsed=time.perf_counter()-start
    assert elapsed<0.26,'complete coalition utility replay stays within the declared local batch budget'
    calls=large.evaluator.calls;expected_by_key={x.coalition:x for x in expected.observations}
    assert len(calls)>=len(set(requests)) and {call.coalition for call in calls}==set(requests) and all(call==expected_by_key[call.coalition]for call in calls),'actual evaluator diagnostics retain legitimate game observations and cover every requested coalition'

@pytest.mark.skip(reason="Part 2")
def test_part2_complete_sqlite_accounting(tmp_path):
    """Reopen the complete accounting snapshot with domain associations, signed exact credits and independent total/surplus fields."""
    full=snapshot();restored=reopen_snapshot(tmp_path,full)
    assert restored==full,'SQLite reopen retains every ordered game criterion observation permutation quality receipt and credit field'
    assert restored.statement.grand==F(8) and restored.statement.surplus==F(1),'stored total value and distributable surplus are separate domain fields'
    assert restored.receipts[0].confirmed is False and restored.receipts[1].quality==F(1,5),'unconfirmed and confirmed evidence remain separate durable observations'
    assert restored.replay.observations[1]==restored.replay.observations[3] and len(restored.replay.observations)==4,'equal coalition requests keep their declared occurrence order'
    assert restored.quantum.as_tuple()==Decimal('0.0100').as_tuple() and restored.unit=='unit,α','synthetic denomination identity and Decimal quantum scale survive close and reopen'
    huge=F(10**80+3,17);changed=replace(full,allocations=(('a',huge),('b',-huge),('null',F(0))),permutations=(),receipts=(),replay=ReplayReport(full.game.uid,(),F(0)))
    path=tmp_path/'replace.sqlite';a=AccountingArchive(path);a.save(full);a.save(changed);a.close();b=AccountingArchive(path)
    assert b.load()==changed,'complete replacement retains exact signed balances while removing earlier observations and evidence'
    b.close()

@pytest.mark.skip(reason="Part 3")
def test_part3_exact_sampled_and_completed_reports(tmp_path):
    """Implement subset-weight marginals, fresh complete permutations and actual-completed block normalization using reopened games."""
    restored=reopen_snapshot(tmp_path);game=restored.game;desk=CreditDesk(game);exact=shapley_exact(game,desk.oracle);report=allocation_report(game,desk.oracle,(exact,))
    assert exact.totals==(F(2),F(-1),F(0)) and report.efficiency==restored.statement,'actual restored game yields signed and null exact marginal allocations'
    assert len(exact.marginals)==12 and sum((x.weight for x in exact.marginals if x.player=='a'),F(0))==1,'each player retains every normalized weighted subset evidence term'
    synergy=Game('synergy',('a','b'),F(5),(Criterion('a',frozenset({'a'}),F(1)),Criterion('b',frozenset({'b'}),F(3)),Criterion('ab',frozenset({'a','b'}),F(6))))
    oracle=CreditDesk(synergy).oracle;block=shapley_exact(synergy,oracle)
    assert block.totals==(F(4),F(6)) and tuple(x.weight for x in block.marginals)==(F(1,2),)*4,'joint synergy is distributed through true signed before-after subset marginals'
    rng=Random(19);sampled=shapley_sampled(synergy,oracle,7,rng);expected_rng=Random(19);orders=[];totals={'a':F(0),'b':F(0)}
    for _ in range(7):
        order=list(synergy.players);expected_rng.shuffle(order);orders.append(tuple(order))
        totals[order[0]]+=F(1)if order[0]=='a'else F(3);totals[order[1]]+=F(7)if order[1]=='a'else F(9)
    assert sampled.permutations==tuple(orders) and sampled.totals==tuple(totals[p]for p in synergy.players) and rng.getstate()==expected_rng.getstate(),'fresh complete seeded permutations retain actual marginal totals and RNG consumption'
    short=shapley_sampled(synergy,oracle,1,Random(3));partial=replace(short,requested=5);combined=allocation_report(synergy,oracle,(sampled,partial))
    expected=tuple((x+y)/8 for x,y in zip(sampled.totals,short.totals))
    assert combined.credits==expected and combined.requested==12 and combined.completed==8 and combined.partial and combined.approximate and combined.efficiency.residual==0,'sample blocks combine their actual completed totals rather than requested counts or equal block means'
    empty_sample=shapley_sampled(synergy,oracle,0,Random(8));empty_report=allocation_report(synergy,oracle,(replace(empty_sample,requested=3),))
    assert empty_report.credits==(F(0),F(0)) and empty_report.completed==0 and empty_report.partial and empty_report.efficiency.residual==10,'zero completed samples remain an explicitly partial estimate with the real residual'
    zero_request=allocation_report(synergy,oracle,(empty_sample,))
    assert zero_request.requested==zero_request.completed==0 and not zero_request.partial and zero_request.approximate and zero_request.efficiency.residual==10,'a zero-size requested sample is approximate but has no uncompleted requested work'
    empty_game=Game('empty',(),F(9),());empty_oracle=CreditDesk(empty_game).oracle
    assert allocation_report(empty_game,empty_oracle,(shapley_exact(empty_game,empty_oracle),)).credits==(),'an empty player roster has a valid empty exact allocation'
    shifted=replace(synergy,uid='shifted',baseline=F(-101))
    assert shapley_exact(shifted,CreditDesk(shifted).oracle).totals==block.totals,'constant game baseline shifts do not change any player marginal'
    empty_rule=replace(synergy,uid='empty-rule',criteria=(Criterion('always',frozenset(),F(11)),*synergy.criteria));er=CreditDesk(empty_rule).oracle
    assert allocation_report(empty_rule,er,(shapley_exact(empty_rule,er),)).efficiency.empty==16 and shapley_exact(empty_rule,er).totals==block.totals,'empty-required criterion utility belongs to the actual empty coalition without creating player credit'

@pytest.mark.skip(reason="Part 4")
def test_part4_actual_sample_block_csv(tmp_path):
    """Project own per-agent block totals, actual completed denominator and exact approximation metadata in CSV."""
    restored=reopen_snapshot(tmp_path);game=restored.game;oracle=CreditDesk(game).oracle;block=replace(shapley_sampled(game,oracle,2,Random(6)),requested=5)
    text=asyncio.run(export_blocks(game,oracle,(block,),restored.unit,restored.quantum));reader=csv.DictReader(io.StringIO(text));rows=list(reader)
    expected_header=('game','agent','total_num','total_den','credit_num','credit_den','requested','completed','mode','partial','residual_num','residual_den','unit','quantum')
    assert tuple(reader.fieldnames)==expected_header and len(rows)==3,'every declared agent owns one complete allocation CSV row for the actual block'
    for i,row in enumerate(rows):
        total=F(int(row['total_num']),int(row['total_den']));credit=F(int(row['credit_num']),int(row['credit_den']))
        assert row['game']==game.uid and row['agent']==game.players[i] and total==block.totals[i] and credit==block.totals[i]/2,'each agent credit uses its own marginal total and the actual completed sample denominator'
        assert row['requested']=='5' and row['completed']=='2' and row['mode']=='sampled' and row['partial']=='True' and row['residual_num']=='0','partial approximate publication retains actual block metadata and supplied efficiency residual'
        assert row['unit']==restored.unit and row['quantum']=='0.0100','CSV quoting preserves synthetic denomination and scale rather than claiming a real payment'
    exact=shapley_exact(game,oracle);exact_rows=list(csv.DictReader(io.StringIO(asyncio.run(export_blocks(game,oracle,(exact,))))))
    assert exact_rows[1]['credit_num']=='-1' and exact_rows[1]['credit_den']=='1' and exact_rows[1]['mode']=='exact' and exact_rows[1]['partial']=='False','negative exact credit remains signed without a sample denominator'
    zero=replace(shapley_sampled(game,oracle,0,Random(0)),requested=4);zero_rows=list(csv.DictReader(io.StringIO(asyncio.run(export_blocks(game,oracle,(zero,))))))
    assert all(r['credit_num']=='0' and r['completed']=='0' and r['partial']=='True' and r['residual_num']=='1'for r in zero_rows),'zero-completion blocks publish real residuals and never divide by zero'

@pytest.mark.skip(reason="Part 5")
def test_part5_nested_direct_child_team_games(tmp_path):
    """Construct nested direct-child games over primitive unions and explain each actual team marginal support."""
    primitive=Game('team-market',('a','b','c'),F(7),(Criterion('a',frozenset({'a'}),F(2)),Criterion('b',frozenset({'b'}),F(4)),Criterion('c',frozenset({'c'}),F(6)),Criterion('ab',frozenset({'a','b'}),F(6))))
    desk=CreditDesk(primitive);pre=shapley_exact(primitive,desk.oracle);report=allocation_report(primitive,desk.oracle,(pre,));base=AccountingSnapshot(primitive,desk.replay((frozenset(),frozenset({'a','b','c'}))),(),(),tuple(zip(primitive.players,report.credits)),report.efficiency)
    restored=reopen_snapshot(tmp_path,base);oracle=CreditDesk(restored.game).oracle
    a,b,c=Primitive('a'),Primitive('b'),Primitive('c');left=Team('left',(a,b));right=Team('right',(b,c));root=Team('root',(left,right));audit=audit_teams(TeamCatalog(restored.game,root),oracle)
    assert pre.totals==(F(5),F(7),F(6)) and audit.credits==(F(10),F(8)) and audit.efficiency.surplus==18,'direct child teams are players of their union-valued game rather than sums of primitive Shapley credits'
    assert audit.members==frozenset({'a','b','c'}) and audit.players==('left','right') and audit.efficiency.residual==0,'overlapping primitive members contribute utility once while direct child player order is preserved'
    assert audit.children[0].credits==(F(5),F(7)) and audit.children[1].credits==(F(4),F(6)) and audit.children[0].members==frozenset({'a','b'}),'each nested team retains its own local characteristic game and allocation'
    term=next(x for x in audit.support if x.child_uid=='left'and x.before_children==frozenset({'right'}))
    assert term.before_members==frozenset({'b','c'}) and term.introduced_members==frozenset({'a'}) and term.after_members==frozenset({'a','b','c'}) and term.marginal==8 and term.weight==F(1,2),'marginal support explains only newly introduced primitive members and the actual local-game difference'
    empty=audit_teams(TeamCatalog(restored.game,Team('empty',())),oracle)
    assert empty.members==frozenset() and empty.players==() and empty.credits==() and empty.efficiency.residual==0,'an empty nested team has no fabricated contributor or allocation'
    wrapper=audit_teams(TeamCatalog(restored.game,Team('wrapper',(root,))),oracle)
    assert wrapper.credits==(F(18),) and wrapper.children[0]==audit,'a one-child wrapper has its own team-game player while preserving the real nested audit'
    signed_game=Game('signed-team',('a','b'),F(9),(Criterion('always',frozenset(),F(5)),Criterion('loss',frozenset({'a'}),F(-2)),Criterion('null',frozenset({'b'}),F(0))))
    signed=audit_teams(TeamCatalog(signed_game,Team('signed-root',(Team('loss-team',(a,)),Team('null-team',(b,))))),CreditDesk(signed_game).oracle)
    assert signed.credits==(F(-2),F(0)) and signed.efficiency.empty==14 and signed.efficiency.residual==0 and signed.children[0].credits==(F(-2),),'nested team games preserve negative and null players with their actual nonzero empty utility'
    three=audit_teams(TeamCatalog(restored.game,Team('three',(a,b,c))),oracle)
    assert three.credits==pre.totals and len(three.support)==12 and all(tuple(x.weight for x in three.support if x.child_uid==player)==(F(1,3),F(1,6),F(1,6),F(1,3))for player in three.players),'each team support retains its actual weighted subset evidence independently of child count'
    primitive_leaf=audit_teams(TeamCatalog(signed_game,a),CreditDesk(signed_game).oracle)
    assert primitive_leaf.members==frozenset({'a'}) and primitive_leaf.players==primitive_leaf.credits==() and primitive_leaf.efficiency==Efficiency('primitive:a',F(14),F(14),F(0),F(0),F(0)) and primitive_leaf.support==primitive_leaf.children==(),'a primitive leaf own zero-player game retains the actual empty coalition accounting'
