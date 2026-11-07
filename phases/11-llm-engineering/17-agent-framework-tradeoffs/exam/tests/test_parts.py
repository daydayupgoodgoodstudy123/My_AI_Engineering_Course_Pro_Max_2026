"""Five locked stages for the fixed-course decision evidence service."""
import asyncio,itertools,json,time
from dataclasses import replace
import pytest
from shapecompass.contracts import (FLAGS,Problem,Scenario,Recommendation,FeatureCard,ReportRow,RuleEvaluation,DecisionCard,finish_decision,decision_json,row_text)

def observed(rule='roles',requirements=('has_roles',)):
    specs=(('hard',False,(('needs_resume',False),('needs_human_interrupt',False),('has_parallel_fanout',False))),('tiny',False,(('total_llm_calls',4),)+tuple((k,k in requirements) for k in FLAGS)),('dialogue',False,(('has_dialogue',False),('has_typed_state',False))),('roles',True,(('has_roles',True),('has_typed_state',False))))
    if rule=='hard':specs=(('hard',True,(('needs_resume',True),('needs_human_interrupt',True),('has_parallel_fanout',True))),)
    return finish_decision(rule,requirements,tuple(RuleEvaluation(*item) for item in specs))

def report_fixture(count=6000):
    rows=tuple(ReportRow('case'+str(i),('wide scenario '+str(i)+'界'*(i%71)),FeatureCard(i%13,tuple((key,bool((i>>j)&1)) for j,key in enumerate(FLAGS))),Recommendation('fixture-profile','observed reason '+str(i))) for i in range(count))
    width=max(60,max(len(row.label) for row in rows))
    expected=''.join(row_text(row,width)+'\n' for row in rows)
    return rows,expected

@pytest.mark.skip('Part 1')
def test_problem_intake_and_complete_comparison_report():
    """Repair descriptor projection, ordered identities and report responsiveness."""
    from shapecompass.intake import decode_problem,prepare_cases,format_case_table
    raw=[{'case_id':'a','label':'same','problem':{'has_roles':True,'total_llm_calls':0}}, {'case_id':'b','label':'same','problem':{'has_typed_state':True,'needs_session_memory':True,'total_llm_calls':2}}]
    seen=[]
    def fixture(problem):
        seen.append(problem)
        return Recommendation('fixture-profile','calls '+str(problem.total_llm_calls))
    rows=prepare_cases(raw,fixture)
    assert tuple((x.case_id,x.features.total_llm_calls,x.features.signals) for x in rows)==(('a',0,tuple((key,key=='has_roles') for key in FLAGS)),('b',2,tuple((key,key in ('has_typed_state','needs_session_memory')) for key in FLAGS))), 'ordered scenario records retain their own identity and all projected features'
    assert seen==[Problem(has_roles=True,total_llm_calls=0),Problem(has_typed_state=True,needs_session_memory=True,total_llm_calls=2)], 'fixture recommenders receive the original complete typed problem descriptors'
    assert decode_problem({})==Problem(), 'declared omitted descriptor defaults survive intake'
    with pytest.raises(ValueError):decode_problem({'has_roles':'false'})
    with pytest.raises(ValueError):decode_problem({'total_llm_calls':True})
    assert format_case_table(())=='', 'an empty comparison report is empty'
    tiny=(replace(rows[0],label='x'),replace(rows[1],label='長'*74))
    assert format_case_table(tiny)==''.join(row_text(row,74)+'\n' for row in tiny), 'all rows share the full batch character layout without truncating long labels'
    prepared,expected=report_fixture()
    started=time.perf_counter();actual=format_case_table(prepared)
    assert actual==expected, 'the completed report preserves every prepared row and all recommendation text'
    elapsed=time.perf_counter()-started
    assert elapsed<0.08, 'large complete comparison reports should stay responsive'

@pytest.mark.skip('Part 2')
def test_ini_catalog_and_bound_decision_evidence(tmp_path):
    """Persist ordered INI problem descriptors and complete case-bound evidence."""
    from shapecompass.catalog import CatalogStore
    scenarios=(Scenario('z','same 100%\n## not a card',Problem(has_roles=True,total_llm_calls=0)),Scenario('a','same 100%\n## not a card',Problem(needs_resume=True,needs_human_interrupt=True,has_parallel_fanout=True,total_llm_calls=2)))
    decisions=(('a',observed('hard',('has_parallel_fanout','needs_resume','needs_human_interrupt'))),('z',observed()))
    CatalogStore(tmp_path).save(scenarios,decisions)
    loaded=CatalogStore(tmp_path).load()
    assert loaded==((scenarios[0],decisions[1][1]),(scenarios[1],decisions[0][1])), 'reopened scenarios keep catalog order exact flags text counts and their own complete decision evidence'
    assert (tmp_path/'scenarios.ini').exists() and (tmp_path/'decisions.json').exists(), 'scenario descriptors and decision evidence use the declared two local artifacts'
    from shapecompass.catalog_io import read_ini,write_ini
    cfg=read_ini(tmp_path/'scenarios.ini');cfg.remove_option('z','has_dialogue');cfg.remove_option('z','needs_session_memory');cfg.remove_option('a','total_llm_calls');write_ini(tmp_path/'scenarios.ini',cfg)
    loaded=CatalogStore(tmp_path).load()
    assert loaded[0][0].problem==scenarios[0].problem and loaded[1][0].problem.total_llm_calls==1, 'omitted optional catalog fields retain the declared descriptor defaults'
    cfg=read_ini(tmp_path/'scenarios.ini');cfg.set('z','has_roles','off');write_ini(tmp_path/'scenarios.ini',cfg)
    assert CatalogStore(tmp_path).load()[0][0].problem.has_roles is False, 'explicit false INI flag spellings preserve false values'
    with pytest.raises(ValueError):CatalogStore(tmp_path/'bad').save(scenarios,decisions[:1])
    with pytest.raises(ValueError):CatalogStore(tmp_path/'dupe').save((scenarios[0],scenarios[0]),decisions)
    assert CatalogStore(tmp_path).load()[1][1]==decisions[0][1], 'all recorded false and true predicate evidence survives repeated reopening'

    specials=(Scenario('DEFAULT','reserved-looking legal ID',Problem(has_roles=True,total_llm_calls=4)),Scenario('default','lowercase identity',Problem(needs_resume=True,total_llm_calls=0)),Scenario('Default','mixed case identity',Problem(has_typed_state=True,total_llm_calls=2)))
    bound=(('Default',observed()),('DEFAULT',observed()),('default',observed('hard',('needs_resume',))))
    CatalogStore(tmp_path/'special').save(specials,bound)
    assert CatalogStore(tmp_path/'special').load()==tuple((row,dict(bound)[row.case_id]) for row in specials), 'every legal case identity including reserved-looking and case-distinct names survives catalog reopening'

    memory=Scenario('session-flags','memory with a specialist',Problem(has_roles=True,needs_session_memory=True,total_llm_calls=4))
    memory_decision=observed(requirements=('has_roles','needs_session_memory'))
    CatalogStore(tmp_path/'memory').save((memory,),(('session-flags',memory_decision),))
    assert CatalogStore(tmp_path/'memory').load()==((memory,memory_decision),), 'session-memory requirements survive a completed catalog save and reopen'
    exact_calls=(1<<53)+1
    precise=Scenario('precise-calls','exact call budget',Problem(has_roles=True,total_llm_calls=exact_calls))
    precise_trace=tuple(replace(step,evidence=tuple((key,exact_calls if key=='total_llm_calls' else item) for key,item in step.evidence)) for step in observed().trace)
    precise_decision=finish_decision('roles',('has_roles',),precise_trace)
    CatalogStore(tmp_path/'precise').save((precise,),(('precise-calls',precise_decision),))
    assert CatalogStore(tmp_path/'precise').load()==((precise,precise_decision),), 'nonnegative integer call counts survive catalog reopening exactly'

@pytest.mark.skip('Part 3')
def test_fixed_course_rule_precedence_and_actual_trace():
    """Implement the course selector with exact evaluated prefix and explanations."""
    from shapecompass.selector import recommend
    cases=((Problem(total_llm_calls=2),'tiny','plain python'),(Problem(has_typed_state=True,total_llm_calls=1),'typed','langgraph'),(Problem(needs_session_memory=True,total_llm_calls=0),'session','agno'),(Problem(has_roles=True,has_dialogue=True,total_llm_calls=4),'dialogue','autogen'),(Problem(has_roles=True,has_dialogue=True,needs_resume=True,has_parallel_fanout=True,needs_human_interrupt=True),'hard','langgraph'),(Problem(has_typed_state=True,needs_session_memory=True,total_llm_calls=2),'session','agno'),(Problem(has_typed_state=True,has_dialogue=True,has_roles=True,needs_session_memory=True),'typed','langgraph'),(Problem(total_llm_calls=3),'fallback','langgraph'))
    for problem,rule,framework in cases:
        decision=recommend(problem)
        assert (decision.decisive_rule,decision.framework)==(rule,framework), 'the declared course priority preserves conflicting state shape and call-budget requirements'
        assert decision.requirements==tuple(key for key in FLAGS if getattr(problem,key)), 'recommendation evidence retains every true requirement in canonical signal order'
        assert decision==finish_decision(rule,decision.requirements,decision.trace), 'framework and complete reason correspond to the actual decisive rule evidence'
    operands={'hard':('needs_resume','needs_human_interrupt','has_parallel_fanout'),'tiny':('total_llm_calls',)+FLAGS,'dialogue':('has_dialogue','has_typed_state'),'roles':('has_roles','has_typed_state'),'session':('needs_session_memory','has_roles','has_dialogue'),'typed':('has_typed_state',),'fallback':()}
    rule_ids=tuple(operands)
    for calls,bits in itertools.product((0,2,3),itertools.product((False,True),repeat=7)):
        values=dict(zip(FLAGS,bits));problem=Problem(**values,total_llm_calls=calls);decision=recommend(problem)
        truth=(any(values[k] for k in operands['hard']),calls<=2 and not any(bits),values['has_dialogue'] and not values['has_typed_state'],values['has_roles'] and not values['has_typed_state'],values['needs_session_memory'] and not values['has_roles'] and not values['has_dialogue'],values['has_typed_state'],True)
        index=truth.index(True);expected=tuple(RuleEvaluation(rule_ids[i],truth[i],tuple((key,getattr(problem,key)) for key in operands[rule_ids[i]])) for i in range(index+1))
        assert decision.trace==expected and decision.decisive_rule==rule_ids[index], 'actual evaluation evidence is exactly the observed prefix through the first matched course rule'
    hard=recommend(Problem(needs_resume=True,needs_human_interrupt=True,has_parallel_fanout=True))
    assert hard.trace==(RuleEvaluation('hard',True,(('needs_resume',True),('needs_human_interrupt',True),('has_parallel_fanout',True))),), 'all satisfied hard requirements are visible without evaluating lower priority guards'

def parse_card(text):
    lines=text.split('\n');assert len(lines)==8 and lines[-1]=='' and lines[0].startswith('## Scenario '), 'one complete card has one isolated heading and six evidence fields'
    label=json.loads(lines[0][12:]);fields={}
    for line in lines[1:-1]:
        key,value=line[2:].split(': ',1);fields[key]=json.loads(value)
    return label,fields

@pytest.mark.skip('Part 4')
def test_isolated_markdown_cards_and_complete_evidence():
    """Project each current decision into one isolated complete Markdown card."""
    from shapecompass.card_driver import stream_cards
    events=(DecisionCard(Scenario('first','title\n## Scenario forged\r\n界',Problem(has_roles=True,total_llm_calls=4)),replace(observed(),reason='role reason\n## forged\t100%')),DecisionCard(Scenario('second','second title',Problem(needs_resume=True)),observed('hard',('needs_resume','needs_human_interrupt','has_parallel_fanout'))))
    class Feed:
        def __init__(self):self.index=0;self.released=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index>=len(events):raise StopAsyncIteration
            if self.index>self.released:raise AssertionError('a complete card is observable before pulling another scenario')
            event=events[self.index];self.index+=1;return event
        async def aclose(self):self.closed+=1
    async def run():
        feed=Feed();stream=stream_cards(feed);first=await stream.__anext__();a=parse_card(first)
        assert a[0]==events[0].scenario.label and first.count('\n## Scenario ')==0, 'scenario and reason text cannot manufacture additional Markdown card headings'
        for index,chunk in enumerate((first,None)):
            if index:feed.released=1;chunk=await stream.__anext__()
            label,fields=parse_card(chunk);event=events[index];raw=decision_json(event.decision)
            assert (label,fields)==(event.scenario.label,{'Case':event.scenario.case_id,'Framework':raw['framework'],'Rule':raw['decisive_rule'],'Requirements':raw['requirements'],'Reason':raw['reason'],'Evaluated':raw['trace']}), 'each complete card retains its own scenario requirements decisive reason and full evaluated evidence'
        with pytest.raises(StopAsyncIteration):await stream.__anext__()
        assert feed.closed==1, 'the given card driver closes an exhausted source'
        feed=Feed();stream=stream_cards(feed);await stream.__anext__();await stream.aclose()
        assert feed.closed==1 and feed.index==1, 'closing a partially consumed card stream closes its current source'
    asyncio.run(run())

    from shapecompass.cards import render_card
    field_lines=render_card(events[0]).split('\n')[1:-1]
    assert tuple(line[2:].split(': ',1)[0] for line in field_lines)==('Case','Framework','Rule','Requirements','Reason','Evaluated'), 'Markdown card evidence fields retain the declared presentation order'

@pytest.mark.skip('Part 5')
def test_nested_observed_decision_path_only():
    """Structure supplied trace evidence without evaluating another recommendation."""
    from shapecompass.explanation import structure_trace
    decision=observed();tree=structure_trace(decision);node=tree;path=()
    for step in decision.trace:
        path=path+(step.rule_id,)
        assert (node['rule_id'],node['path'],node['matched'],node['evidence'])==(step.rule_id,path,step.matched,step.evidence), 'nested explanation preserves every observed false guard operand and exact branch path'
        edge='true' if step.matched else 'false'
        assert set(node)=={'rule_id','path','matched','evidence',edge}, 'only the observed branch is present at each course rule'
        node=node[edge];path=path+(edge,)
    assert node=={'path':path,'framework':decision.framework,'decisive_rule':'roles','reason':decision.reason,'requirements':decision.requirements}, 'the decisive leaf keeps the selected rule and its actual scenario evidence'
    hard=observed('hard',('needs_resume',));direct=structure_trace(hard)
    assert direct['true']['path']==('hard','true') and 'false' not in direct, 'a high priority match has no invented later evaluations'
    with pytest.raises(ValueError):structure_trace(replace(decision,trace=decision.trace[1:]))
    with pytest.raises(ValueError):structure_trace(replace(decision,trace=decision.trace[:-1]))
    with pytest.raises(ValueError):structure_trace(replace(hard,trace=hard.trace+decision.trace[1:]))
    with pytest.raises(ValueError):structure_trace(replace(decision,decisive_rule='typed',framework='langgraph'))
    assert direct['true']['decisive_rule']=='hard' and direct['true']['reason']==hard.reason, 'different rules selecting the graph profile retain their own decisive evidence'
