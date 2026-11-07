"""Three independent control interpreters over identical corrected primitive interfaces."""
from copy import deepcopy
from .models import step_range
from .control import resolve_target

def replay_static(team,state,order,max_steps=10):
    """Use only external order, ignoring returned handoffs; record complete state and stop reason."""
    decisions=[];reason='order-complete'
    for step in step_range(max_steps):
        if step>=len(order):break
        speaker=order[step];target=resolve_target(speaker,team)
        if target.kind!='next':reason='unknown';break
        message=team[speaker].run(state);state.append(message)
        next_name=order[step+1] if step+1<len(order) else None
        decisions.append({'mode':'static','step':step,'speaker':speaker,'message':deepcopy(message),'static_next':next_name,'selector_choice':None,'available':list(team)})
    else:
        if len(order)>max_steps:reason='budget'
    return {'mode':'static','decisions':decisions,'stop':{'mode':'static','reason':reason,'executed':len(decisions),'last_speaker':decisions[-1]['speaker'] if decisions else None},'messages':state.snapshot()}

def replay_handoffs(team,state,start,max_steps=10):
    """Follow each returned handoff, preserving explicit done/unknown/budget outcomes."""
    decisions=[];current=start;reason='budget'
    for step in step_range(max_steps):
        target=resolve_target(current,team)
        if target.kind!='next':reason=target.kind;break
        message=team[current].run(state);state.append(message)
        decisions.append({'mode':'handoff','step':step,'speaker':current,'message':deepcopy(message),'static_next':None,'selector_choice':None,'available':list(team)})
        target=resolve_target(message.get('handoff','done'),team)
        if target.kind!='next':reason=target.kind;break
        current=target.name
    return {'mode':'handoff','decisions':decisions,'stop':{'mode':'handoff','reason':reason,'executed':len(decisions),'last_speaker':decisions[-1]['speaker'] if decisions else None},'messages':state.snapshot()}

def replay_selector(team,state,start,selector,max_steps=10):
    """Append before selecting from updated shared state; ignore returned handoff control."""
    decisions=[];current=start;reason='budget'
    for step in step_range(max_steps):
        target=resolve_target(current,team)
        if target.kind!='next':reason=target.kind;break
        message=team[current].run(state);state.append(message)
        selected=selector(state,team)
        decisions.append({'mode':'selector','step':step,'speaker':current,'message':deepcopy(message),'static_next':None,'selector_choice':selected,'available':list(team)})
        target=resolve_target(selected,team)
        if target.kind!='next':reason=target.kind;break
        current=target.name
    return {'mode':'selector','decisions':decisions,'stop':{'mode':'selector','reason':reason,'executed':len(decisions),'last_speaker':decisions[-1]['speaker'] if decisions else None},'messages':state.snapshot()}
