"""GIVEN finite intake, independent agent construction and prior-round snapshots."""
import math
from .models import Agent,FrozenAgent

def finite_number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError('numeric input required')
    number=float(value)
    if not math.isfinite(number):raise ValueError('finite numeric input required')
    return number

def initial_team(rows):
    """Return finite unique named states; confidences are scripted weights in[0,1]."""
    states=[];names=set()
    for name,answer,confidence in rows:
        if not isinstance(name,str) or not name or name in names:raise ValueError('unique nonempty agent names required')
        names.add(name);a=finite_number(answer);c=finite_number(confidence)
        if not 0<=c<=1:raise ValueError('confidence outside interval')
        states.append(FrozenAgent(name,a,c))
    if not states:raise ValueError('nonempty team required')
    return tuple(states)

def new_agents(initial):return [Agent(a.name,a.answer,a.confidence) for a in initial]
def frozen_round(agents):return tuple(FrozenAgent(a.name,a.answer,a.confidence) for a in agents)
def requested_rounds(rounds):
    if isinstance(rounds,bool) or not isinstance(rounds,int) or rounds<0:raise ValueError('nonnegative integer rounds required')
    return rounds
