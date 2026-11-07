"""GIVEN complete finite replay lookup, explicit field presence and revision construction."""
from dataclasses import replace

def step_named(state,name):
    for step in state.steps:
        if step.step_id==name:return step
    raise ValueError('unknown step')
def replace_step(state,step):return replace(state,steps=tuple(step if old.step_id==step.step_id else old for old in state.steps))
def required_missing(spec,names):
    fields=dict(spec.fields);rules={r.name:r for r in spec.rules}
    if any(n not in rules for n in names):raise ValueError('undeclared required field')
    return tuple(n for n in names if rules[n].required and n not in fields)
def field_owner(spec,name):
    for rule in spec.rules:
        if rule.name==name:return rule.owner
    raise ValueError('unknown field')
def question_id(spec,step_id,field):return f'{spec.spec_id}@{spec.revision}:{step_id}:{field}'
def answered_revision(spec,field,value):
    if spec.revision>=2:raise ValueError('finite clarification revision budget exhausted')
    values=dict(spec.fields);values[field]=value
    return replace(spec,revision=spec.revision+1,fields=tuple(values.items()))
