"""Five sequential numeric-debate tasks; no source script, LLM or network is run.

Part1: raw numeric records, agreement/truth diagnostics and scalar diameter.
Part2: named binary64 round vectors and independent truth metadata.
Part3: stable weighted revise, capped confidence/history and fixed extra rounds.
Part4: CSV domain rows from complete sealed vectors, with a supplied async driver.
Part5: compact weighted derivation DAG and initial causal inputs, with given identities.
"""
import asyncio,csv,io,json,math,time
import pytest

@pytest.mark.skip('Part 1')
def test_complete_numeric_round_reports():
    """Display does not replace numeric state, and agreement is independent of truth."""
    from mindsync.intake import initial_team
    from mindsync.service import RoundDesk
    from mindsync.fixture import diagnostic_fixture
    team=initial_team((('precise',1.23456789012345,0.6),('peer',2.0,0.4)))
    report=RoundDesk().record(0,team,42.0)
    assert report['record'].agents==team and report['record'].agents[0].answer.hex()==team[0].answer.hex(), 'raw numeric answers retain full precision independently of final display'
    assert report['display']==('precise: 1.23 (0.600)','peer: 2.00 (0.400)'), 'numeric rendering is a final presentation of raw state'
    tight=initial_team((('A',40.0,0.6),('B',40.0,0.8),('C',40.0,0.4)))
    wrong=RoundDesk().record(1,tight,42.0)
    assert wrong['agreement']==1.0 and wrong['truth_error']==2.0 and wrong['correct'] is False, 'unanimous agreement does not certify a wrong answer'
    assert RoundDesk().record(1,tight,None)['correct'] is None and RoundDesk().record(1,tight,None)['truth_error'] is None, 'absent truth does not fabricate correctness or error'
    singleton=RoundDesk().record(0,initial_team((('only',0.0,1.0),)),0.0)
    assert singleton['diameter']==0.0 and singleton['correct'] is True, 'single participant and zero truth remain valid numeric observations'
    args,expected=diagnostic_fixture();started=time.perf_counter()
    complete=RoundDesk().record(*args)
    assert complete==expected, 'complete reports retain every participant, raw record, display and diagnostic field'
    elapsed=time.perf_counter()-started
    assert elapsed<0.1, 'complete finite population diagnostics remain responsive'

@pytest.mark.skip('Part 2')
def test_named_binary64_round_archive(tmp_path):
    """Named answer/confidence alignment owns each round independently of local order."""
    from mindsync.models import FrozenAgent,RoundRecord,DebateArchive
    from mindsync.archive import save_debate,load_debate
    names=('β,一\nagent','A')
    first=RoundRecord(0,(FrozenAgent(names[0],-0.0,0.5),FrozenAgent(names[1],5e-324,1.0)),0.0)
    last=RoundRecord(2,(FrozenAgent(names[0],1.0000000000000002,0.125),FrozenAgent(names[1],-5e-324,0.75)),None)
    before=DebateArchive(names,(first,last));path=tmp_path/'debate.bin';save_debate(path,before);after=load_debate(path)
    assert after==before and after.names==names and tuple(r.index for r in after.records)==(0,2), 'reopening retains declared name order and every sealed round including initial state'
    assert tuple((a.answer.hex(),a.confidence.hex()) for r in after.records for a in r.agents)==tuple((a.answer.hex(),a.confidence.hex()) for r in before.records for a in r.agents), 'binary64 fields roundtrip exactly through the supplied scalar codec'
    assert after.records[0].truth==0.0 and after.records[1].truth is None, 'truth remains separate from debate answer and confidence vectors'
    permuted=DebateArchive(names,(RoundRecord(0,tuple(reversed(first.agents)),first.truth),RoundRecord(2,tuple(reversed(last.agents)),last.truth)))
    second=tmp_path/'permuted.bin';save_debate(second,permuted);aligned=load_debate(second)
    assert aligned==before, 'each answer and confidence pair follows its agent name across locally permuted rounds'
    assert len(path.read_bytes())==len(second.read_bytes()) and path.read_bytes()==second.read_bytes(), 'equivalent aligned vectors have identical complete binary records'
    steady=(FrozenAgent('steady',7.0,1.0),)
    repeated=DebateArchive(('steady',),tuple(RoundRecord(i,steady,None) for i in range(3)))
    repeated_path=tmp_path/'unchanged.bin';save_debate(repeated_path,repeated);reopened=load_debate(repeated_path)
    assert reopened==repeated and tuple(r.index for r in reopened.records)==(0,1,2), 'unchanged sealed vectors retain each completed round'

@pytest.mark.skip('Part 3')
def test_weighted_revision_and_fixed_rounds(tmp_path):
    """Every requested frozen round updates weighted answers, own confidence and history."""
    from mindsync.intake import initial_team
    from mindsync.dynamics import revise_agent,run_numeric_debate
    from mindsync.models import RoundRecord,DebateArchive
    from mindsync.archive import save_debate,load_debate
    simple=initial_team((('A',38.0,0.5),('B',42.5,1.0),('C',51.0,0.5)))
    assert revise_agent(simple[0],simple[1:])==43.5, 'weighted revise includes own answer and correctly paired peer confidences'
    residual=initial_team((('big',1e16,1.0),('residual',1.0,1.0),('negative',-1e16,1.0)))
    assert revise_agent(residual[0],residual[1:])==1/3, 'stable confidence accumulation retains mixed-scale cancellation residuals'
    tiny=initial_team((('big',1e308,1.0),('residual',1e-200,1.0),('negative',-1e308,1.0)))
    assert math.isclose(revise_agent(tiny[0],tiny[1:]),1e-200/3,rel_tol=1e-15), 'representable finite residuals survive extreme cancellation'
    huge=initial_team((('left',1.7e308,1.0),('right',1.7e308,1.0)))
    assert revise_agent(huge[0],huge[1:])==1.7e308, 'a finite convex answer does not overflow intermediate weighted accumulation'
    zero=initial_team((('ignored',1e308,0.0),('anchor',2.0,1.0)))
    assert revise_agent(zero[0],zero[1:])==2.0, 'zero confidence contributes no weighted answer'
    with pytest.raises(ValueError,match='positive total confidence'):revise_agent(initial_team((('x',1.0,0.0),))[0],())
    team=initial_team((('A',38.0,0.6),('B',42.5,0.8),('C',51.0,0.4)))
    path=tmp_path/'initial.bin';save_debate(path,DebateArchive(tuple(a.name for a in team),(RoundRecord(0,team,42.0),)))
    team=load_debate(path).records[0].agents
    run=run_numeric_debate(team,5,42.0)
    assert tuple(r['record'].index for r in run['rounds'])==tuple(range(6)), 'exactly requested extra rounds are retained even after numerical agreement'
    assert all(math.isclose(a.answer,42.888888888888886,rel_tol=1e-15) for a in run['agents']), 'all to all frozen own plus others reaches one shared weighted mean after the first exchange'
    assert all(a.history[0]==initial.answer and len(a.history)==6 and all(value==a.answer for value in a.history[1:]) for a,initial in zip(run['agents'],team)), 'history contains the initial answer and every committed revised answer once'
    assert all(math.isclose(a.confidence,min(initial.confidence*1.05**5,1.0),rel_tol=1e-15) for a,initial in zip(run['agents'],team)), 'each agent grows its own confidence and respects the cap'
    assert run['rounds'][0]['record'].agents==team and run['rounds'][-1]['agreement']==1.0 and run['rounds'][-1]['correct'] is False, 'sealed records keep evaluation separate from scripted agreement'
    initial_only=run_numeric_debate(team,0,None)
    assert len(initial_only['rounds'])==1 and all(a.history==[initial.answer] and a.confidence==initial.confidence for a,initial in zip(initial_only['agents'],team)), 'zero requested exchanges records only the independent initial state'
    capped=run_numeric_debate(initial_team((('near-cap',7.0,0.99),)),1,7.0)
    assert capped['agents'][0].confidence==1.0 and capped['agents'][0].history==[7.0,7.0], 'confidence capping does not erase a committed single-agent round'

@pytest.mark.skip('Part 4')
def test_sealed_round_csv_projection():
    """Agent and diagnostic CSV rows share the same complete sealed round statistics."""
    from mindsync.intake import initial_team
    from mindsync.dynamics import run_numeric_debate
    from mindsync.stream import RoundProjection
    from mindsync.wire_support import encode_rounds,HEADER,scalar_text
    reports=run_numeric_debate(initial_team((('A,一',38.0,0.6),('B',42.5,0.8),('C',51.0,0.4))),1,42.0)['rounds']
    class Source:
        def __init__(self):self.i=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.i==len(reports):raise StopAsyncIteration
            row=reports[self.i];self.i+=1;return row
        async def aclose(self):self.closed+=1
    async def collect():
        source=Source();stream=encode_rounds(source,RoundProjection());chunks=[await anext(stream)]
        assert source.i==0, 'the supplied CSV header precedes sealed round consumption'
        chunks.append(await anext(stream))
        assert source.i==1, 'the supplied driver publishes current sealed round rows before pulling another vector'
        async for chunk in stream:chunks.append(chunk)
        assert source.closed==1, 'the supplied round driver closes its source once'
        return b''.join(chunks)
    rows=list(csv.reader(io.StringIO(asyncio.run(collect()).decode('utf-8'))))
    expected=[]
    for report in reports:
        record=report['record'];agreement=scalar_text(report['agreement']);error=scalar_text(report['truth_error'])
        expected.extend([[str(record.index),a.name,scalar_text(a.answer),scalar_text(a.confidence),agreement,error]for a in record.agents])
        expected.append([str(record.index),'','','',agreement,error])
    assert rows[0]==list(HEADER) and rows[1:]==expected, 'every agent row and the single diagnostic row retain one complete sealed vector and its statistics'
    unknown=run_numeric_debate(initial_team((('only',0.0,1.0),)),0,None)['rounds'][0]
    assert RoundProjection().rows(unknown)==((0,'only','0.0','1.0','1.0',''),(0,'','','','1.0','')), 'initial numeric rows preserve absent truth without a synthetic completed exchange'

@pytest.mark.skip('Part 5')
def test_compact_round_derivation_dag(tmp_path):
    """Shared vector DAG links use prior confidences and trace genuine initial inputs."""
    from mindsync.intake import initial_team
    from mindsync.dynamics import run_numeric_debate
    from mindsync.archive import save_debate,load_debate
    from mindsync.models import DebateArchive
    from mindsync.derivation import build_round_derivation,trace_initial_inputs
    team=initial_team((('silent',99.0,0.0),('anchor',2.0,1.0),('peer',4.0,0.5)))
    run=run_numeric_debate(team,3,12345.0);records=tuple(r['record']for r in run['rounds'])
    path=tmp_path/'sealed.bin';save_debate(path,DebateArchive(tuple(a.name for a in team),records));records=load_debate(path).records
    graph=build_round_derivation(records)
    assert tuple(graph['nodes'])==(0,1,2,3) and graph['nodes'][0]['previous'] is None and graph['nodes'][0]['weights']==(), 'one initial vector and one shared node per committed round form the derivation DAG'
    assert graph['nodes'][2]['previous'] is graph['nodes'][1] and graph['nodes'][3]['previous'] is graph['nodes'][2], 'numeric derivations reference the shared prior vector instead of recursively copying it per agent'
    assert graph['nodes'][2]['weights']==tuple((a.name,a.confidence)for a in records[1].agents), 'edge weights belong to the previous sealed round rather than updated confidence'
    traced=trace_initial_inputs(graph,3,'silent')
    assert traced['target']==(3,'silent') and traced['value']==run['agents'][0].answer and traced['initial_inputs']==((0,'anchor',2.0),(0,'peer',4.0)), 'only nonzero confidence ancestry supplies the requested revised numeric answer'
    assert len(traced['nodes'])==4 and all(node is graph['nodes'][node['round']]for node in traced['nodes']), 'explanation shares compact vector nodes while retaining all temporal steps'
    assert trace_initial_inputs(graph,0,'silent')['initial_inputs']==((0,'silent',99.0),), 'an initial target depends on its own answer before any debate exchange'
    assert all(value!=12345.0 for index,name,value in traced['initial_inputs']), 'truth is evaluation metadata and never a weighted evidence input'
    ordered_team=initial_team((('zeta',4.0,1.0),('alpha',2.0,0.5),('silent',99.0,0.0)))
    ordered_run=run_numeric_debate(ordered_team,1,None)
    ordered_graph=build_round_derivation(tuple(r['record'] for r in ordered_run['rounds']))
    assert trace_initial_inputs(ordered_graph,1,'silent')['initial_inputs']==((0,'zeta',4.0),(0,'alpha',2.0)), 'causal roots retain the original agent order'
