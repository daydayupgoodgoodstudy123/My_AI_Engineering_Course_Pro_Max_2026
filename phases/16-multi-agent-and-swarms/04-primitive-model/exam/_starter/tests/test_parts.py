import asyncio,json
from copy import deepcopy
from time import perf_counter
import pytest
from primswap.models import AgentDefinition,RunConfig,Target
from primswap.agent import Agent
from primswap.state import SharedState
from primswap.control import resolve_target
from primswap.service import SingleStepDesk,ReviewDesk
from primswap.configuration import PrimitiveConfiguration
from primswap.replay import replay_static,replay_handoffs,replay_selector
from primswap.stream import DecisionProjection
from primswap.wire_support import stream_decisions,replay_events
from primswap.composition import flatten_composition

def policy_team():
    def research(state):
        old=state.last_by('researcher')
        return {'content':'new facts 世界','handoff':'writer' if old is None else 'done'}
    def write(state):
        research=state.last_by('researcher')
        return {'content':'Draft summarizing: '+research['content'],'handoff':'reviewer'}
    def review(state):return {'content':'reviewed','handoff':'done'}
    definitions=[AgentDefinition('researcher','Gather facts.',('lookup','read'),'research'),AgentDefinition('writer','Write from evidence.',('draft',),'write'),AgentDefinition('reviewer','Review output.',(),'review')]
    registry={'research':research,'write':write,'review':review}
    return definitions,registry

def persisted_team(path):
    definitions,registry=policy_team();store=PrimitiveConfiguration(path)
    store.save(definitions,RunConfig('static',('researcher','writer','reviewer'),'researcher',5));store.close()
    reopened=PrimitiveConfiguration(path);definitions,config,team=reopened.load(registry);reopened.close()
    return config,team

def parse_sequence(frame):
    assert frame[:1]==b'\x1e' and frame[-1:]==b'\n', 'the supplied serializer produces a complete JSON Text Sequence record'
    return json.loads(frame[1:-1].decode('utf-8'))

def review_fixture():
    history=[{'id':'draft-1','from':'writer','content':'Draft summarizing: original evidence'}]
    history.extend({'id':f'log-{index}','from':'logger','content':f'observed event {index}'} for index in range(30000))
    writers=('writer','writer','absent','logger')
    requests=[{'request_id':f'q-{index}','writer':writers[index%4]} for index in range(2400)]
    expected=[]
    for request in requests:
        name=request['writer'];message=history[0] if name=='writer' else history[-1] if name=='logger' else None
        expected.append({'request_id':request['request_id'],'writer':name,'draft':None if message is None else message['content'],
            'message_id':None if message is None else message['id'],'verdict':'missing' if message is None else 'approved' if name=='writer' else 'needs revision'})
    return history,requests,expected

@pytest.mark.skip('Part 1')
def test_owned_primitives_and_latest_review():
    """Repair shared views, canonical sender, target outcomes and complete latest-draft review."""
    seed={'id':'seed','from':'researcher','content':'accepted facts','payload':{'sources':['local']}}
    state=SharedState([seed]);desk=SingleStepDesk()
    def policy(shared):
        view=shared.snapshot();view.clear()
        return {'id':'draft','from':'reviewer','content':'Draft summarizing: accepted facts','handoff':'done'}
    writer=Agent('writer','Write.',('draft',),policy)
    receipt=desk.execute(writer,state,'researcher')
    assert receipt['evidence']=='accepted facts' and receipt['message']['from']=='writer', 'the invoked writer retains its canonical sender while prior shared evidence remains available'
    assert desk.resolve_handoff({'handoff':'missing'},{'writer':writer})=={'kind':'unknown','target':'missing','successful_stop':False}, 'an unknown handoff target remains an explicit unsuccessful outcome'
    assert resolve_target('done',{'writer':writer})==Target('done',None) and resolve_target(None,{'writer':writer})==Target('selector-stop',None), 'explicit agent completion and an external selector stop remain distinct outcomes'
    view=state.snapshot();view[0]['payload']['sources'].append('edited');last=state.last_by('writer');last['content']='edited'
    assert state.snapshot()[0]['payload']=={'sources':['local']} and state.last_by('writer')['content'].startswith('Draft summarizing:'), 'nested snapshots and latest-message reads do not export mutable shared storage'
    state.append({'id':'draft-2','from':'writer','content':'needs revision'})
    assert state.last_by('writer')['id']=='draft-2' and state.last_by('not-here') is None and len(state.snapshot())==3, 'latest sender observations update after append without deleting full shared history'
    history,requests,expected=review_fixture();pool=SharedState(history);service=ReviewDesk(pool)
    start=perf_counter();actual=[service.review(request) for request in requests]
    assert actual==expected, 'every review returns its requested writer draft identity content and verdict'
    elapsed=perf_counter()-start
    assert elapsed<0.045, 'complete repeated latest-draft reviews remain responsive'
    assert pool.snapshot()==history and len(pool.snapshot())==30001, 'review acceleration retains the complete inspectable message pool'
    newest={'id':'draft-3','from':'writer','content':'Draft summarizing: newest'};pool.append(newest);newest['content']='edited'
    assert service.review({'request_id':'after','writer':'writer'})=={'request_id':'after','writer':'writer','draft':'Draft summarizing: newest','message_id':'draft-3','verdict':'approved'}, 'a newly appended writer draft replaces the earlier review observation with owned data'

@pytest.mark.skip('Part 2')
def test_durable_primitive_configuration(tmp_path):
    """Store exact immutable agent metadata and separately configured control, then rebind named policies."""
    path=tmp_path/'primitives';store=PrimitiveConfiguration(path)
    def local(state):return {'content':'local','handoff':'done'}
    definitions=[AgentDefinition('agent:世界','  prompt 世界\n',('write','read'),'shared-policy'),AgentDefinition('other','  prompt 世界\n',('read','write'),'shared-policy')]
    config=RunConfig('selector',('other','agent:世界'),'',0)
    store.save(definitions,config);store.close();store=PrimitiveConfiguration(path)
    loaded,restored,team=store.load({'shared-policy':local})
    assert loaded==definitions and restored==config, 'dbm reopening restores every immutable definition and exact orchestrator configuration'
    assert team['agent:世界'].policy is local and team['other'].policy is local and team['agent:世界'].tools==('write','read'), 'named runtime policies are rebound without serializing callables or merging ordered tool definitions'
    assert restored.start=='' and restored.max_steps==0 and loaded[0].system_prompt.encode('utf-8')==b'  prompt \xe4\xb8\x96\xe7\x95\x8c\n', 'supplied UTF8 storage preserves original prompt bytes and explicit start metadata'
    with pytest.raises(ValueError,match='unknown local policy'):store.load({})
    row=store.database.get('run','config');row['version']=99;store.database.put('run','config',row)
    with pytest.raises(ValueError,match='unsupported primitive configuration version'):store.load({'shared-policy':local})
    row['version']=1;store.database.put('run','config',row)
    other=store.database.get('agent','other');other['version']=2;store.database.put('agent','other',other)
    with pytest.raises(ValueError,match='unsupported primitive configuration version'):store.load({'shared-policy':local})
    store.close()
    ordered=[definitions[1],definitions[0]];ordered_store=PrimitiveConfiguration(tmp_path/'ordered-definitions')
    ordered_store.save(ordered,RunConfig('static',('other','agent:世界'),None,2))
    ordered_loaded,ordered_config,ordered_team=ordered_store.load({'shared-policy':local});ordered_store.close()
    assert ordered_loaded==ordered and list(ordered_team)==['other','agent:世界'], 'durable definition order remains independent of agent spelling'

@pytest.mark.skip('Part 3')
def test_three_control_origins(tmp_path):
    """Replay identical policies with static returned-handoff and external-selector control."""
    config,team=persisted_team(tmp_path/'team')
    seed=[{'id':'earlier','from':'researcher','content':'prior facts'}]
    static=replay_static(team,SharedState(seed),config.order,config.max_steps)
    handoff=replay_handoffs(team,SharedState(seed),config.start,config.max_steps)
    seen=[]
    def selector(state,agents):
        snapshot=state.snapshot();seen.append((len(snapshot),snapshot[-1]['from']))
        return 'reviewer' if snapshot[-1]['from']=='researcher' else None
    selected=replay_selector(team,SharedState(seed),config.start,selector,config.max_steps)
    assert [event['speaker'] for event in static['decisions']]==['researcher','writer','reviewer'] and static['stop']['reason']=='order-complete', 'static control follows the supplied order even when an agent returns done'
    assert [event['speaker'] for event in handoff['decisions']]==['researcher'] and handoff['stop']['reason']=='done', 'handoff control alone follows the current agent returned successor or completion'
    assert [event['speaker'] for event in selected['decisions']]==['researcher','reviewer'] and selected['stop']['reason']=='selector-stop' and seen==[(2,'researcher'),(3,'reviewer')], 'external selection sees each appended message and alone determines the next speaker'
    assert [event['mode'] for event in static['decisions']]==['static']*3 and [event['step'] for event in selected['decisions']]==[0,1] and seed==[{'id':'earlier','from':'researcher','content':'prior facts'}], 'each replay retains its own control origin position and unchanged initial state'
    cyclic={'a':Agent('a','',(),lambda state:{'content':'a','handoff':'b'}),'b':Agent('b','',(),lambda state:{'content':'b','handoff':'a'})}
    limited=replay_handoffs(cyclic,SharedState(),'a',3)
    assert [event['speaker'] for event in limited['decisions']]==['a','b','a'] and limited['stop']=={'mode':'handoff','reason':'budget','executed':3,'last_speaker':'a'}, 'bounded handoff replay reports truncation separately from normal completion'
    unknown={'a':Agent('a','',(),lambda state:{'content':'a','handoff':'not-present'})}
    assert replay_handoffs(unknown,SharedState(),'a',3)['stop']['reason']=='unknown', 'repaired target resolution remains visible as an unsuccessful replay stop'
    zero=replay_selector(team,SharedState(seed),'researcher',lambda state,agents:pytest.fail('unexpected selector'),0)
    assert zero['decisions']==[] and zero['messages']==seed and zero['stop']['reason']=='budget', 'the given zero step budget performs no policy or selector work'
    assert selected['messages'][-1]['from']=='reviewer' and selected['stop']['executed']==2 and selected['decisions'][0]['selector_choice']=='reviewer', 'completed messages and observed selector choices remain in the replay result'
    repeated_team={'a':Agent('a','',(),lambda shared:{'content':str(len(shared.snapshot())),'handoff':'done'})}
    repeated=replay_static(repeated_team,SharedState(),('a','a'),2)
    assert [event['speaker'] for event in repeated['decisions']]==['a','a'] and [message['content'] for message in repeated['messages']]==['0','1'] and repeated['stop']=={'mode':'static','reason':'order-complete','executed':2,'last_speaker':'a'}, 'each repeated static path occurrence executes against current shared history'
    previous=[{'id':f'previous-{index}','from':'history','content':'already observed'} for index in range(3)]
    resumed=replay_handoffs(cyclic,SharedState(previous),'a',2)
    assert [event['speaker'] for event in resumed['decisions']]==['a','b'] and resumed['messages'][:3]==previous and resumed['stop']=={'mode':'handoff','reason':'budget','executed':2,'last_speaker':'b'}, 'preexisting messages do not spend the current handoff execution budget'

@pytest.mark.skip('Part 4')
def test_selected_control_json_sequence(tmp_path):
    """Project decision control from its true source and encode typed stop records through a given driver."""
    config,team=persisted_team(tmp_path/'wire-team');result=replay_static(team,SharedState(),config.order,5)
    events=list(replay_events(result));projection=DecisionProjection()
    first=projection.decision(events[0]['value'])
    assert first['control']=={'origin':'static','requested':'writer','outcome':'next','next_agent':'writer'} and first['message']==result['decisions'][0]['message'], 'a static decision describes external order and its actual message'
    varied=deepcopy(result['decisions'][0]);varied.update({'mode':'selector','static_next':'writer','selector_choice':'reviewer'})
    assert projection.decision(varied)['control']=={'origin':'selector','requested':'reviewer','outcome':'next','next_agent':'reviewer'}, 'selector control is reported independently of returned handoff and static order'
    varied.update({'mode':'handoff','selector_choice':'reviewer'});varied['message']['handoff']='done'
    assert projection.decision(varied)['control']=={'origin':'handoff','requested':'done','outcome':'done','next_agent':None}, 'a handoff completion is not an external successor selection'
    original=deepcopy(varied);payload=projection.decision(varied);payload['message']['content']='edited'
    assert varied==original, 'published decision messages own their source snapshot'
    async def exercise():
        state={'pulled':0,'closed':False}
        async def source():
            try:
                for event in events:state['pulled']+=1;yield event
            finally:state['closed']=True
        output=stream_decisions(source(),projection);wire=await output.__anext__()
        assert parse_sequence(wire)==first and state['pulled']==1, 'the given driver publishes a complete current decision before pulling another'
        await output.aclose()
        assert state=={'pulled':1,'closed':True}, 'the given driver closes the decision source without observing a future event'
        decoded=[parse_sequence(frame) async for frame in stream_decisions(source(),projection)]
        assert [record['step'] for record in decoded[:-1]]==[0,1,2] and all(record['kind']=='decision' for record in decoded[:-1]), 'the ordered decision records retain their complete original control positions'
        assert decoded[-1]=={'kind':'stop','mode':'static','reason':'order-complete','executed':3,'last_speaker':'reviewer'}, 'a typed terminal record retains run reason count and last speaker separately from messages'
    asyncio.run(exercise())
    last=projection.decision(result['decisions'][-1])
    assert last['control']['outcome']=='order-complete' and last['control']['requested'] is None, 'the final static decision reports the end of external order rather than the returned handoff'
    nested=deepcopy(varied);nested['message']['payload']={'sources':['local']};nested_original=deepcopy(nested)
    nested_record=projection.decision(nested);nested_record['message']['payload']['sources'].append('edited')
    assert nested==nested_original, 'projected nested message payloads remain owned after publication'

@pytest.mark.skip('Part 5')
def test_nested_primitive_ownership(tmp_path):
    """Flatten scoped primitive composition while retaining intended shared stores and scheduler inheritance."""
    config,team=persisted_team(tmp_path/'composition-team')
    stores={'global':SharedState(),'isolated':SharedState()}
    shared={'kind':'agent','name':'writer','agent':'writer'}
    root={'kind':'group','name':'root','store':'global','scheduler':'static','children':[
        {'kind':'group','name':'left','scheduler':'handoff','children':[shared]},
        {'kind':'group','name':'right','children':[shared]},
        {'kind':'group','name':'private','store':'isolated','scheduler':'selector','children':[{'kind':'agent','name':'writer','agent':'reviewer'}]}]}
    leaves=flatten_composition(root,stores,'global','static')
    assert [leaf['scope'] for leaf in leaves]==[('root','left','writer'),('root','right','writer'),('root','private','writer')], 'nested scopes retain repeated short agent names and reused acyclic subtrees'
    assert [(leaf['agent'],leaf['store_id'],leaf['scheduler']) for leaf in leaves]==[('writer','global','handoff'),('writer','global','static'),('reviewer','isolated','selector')], 'each leaf inherits its actual state-store and scheduler ownership independently'
    assert leaves[0]['store'] is leaves[1]['store'] is stores['global'] and leaves[2]['store'] is stores['isolated'], 'intentional shared store references remain the original objects while isolated stores remain distinct'
    stores['global'].append({'id':'shared-message','from':'researcher','content':'evidence'})
    assert leaves[1]['store'].last_by('researcher')['content']=='evidence' and leaves[2]['store'].snapshot()==[], 'sharing a store shares later observations without leaking into a separately owned pool'
    cyclic={'kind':'group','name':'cycle','children':[]};cyclic['children'].append(cyclic)
    with pytest.raises(ValueError,match="composition cycle at .*cycle.*cycle"):flatten_composition(cyclic,stores,'global','static')
    duplicate={'kind':'group','name':'duplicates','children':[shared,deepcopy(shared)]}
    with pytest.raises(ValueError,match='duplicate composition child'):flatten_composition(duplicate,stores,'global','static')
    with pytest.raises(ValueError,match='unknown composition store'):flatten_composition({'kind':'agent','name':'x','agent':'writer','store':'missing'},stores,'global','static')
    assert team[leaves[0]['agent']].name=='writer' and team[leaves[2]['agent']].name=='reviewer' and config.mode=='static', 'persisted primitive definitions remain addressable independently of nested control ownership'
