"""Local observation, decision, joint collection and obstacle-free distance contracts."""
from collections import deque
from .models import Observation
from .world_support import q_lookup,local_argmax,collect_one

def encode_local_observation(raw):
    """Preserve the declared actor's row/column coordinates and target identity."""
    return Observation(raw.agent_uid,raw.size,raw.cell,raw.target)

def local_actor(observation,table,critic_hint):
    """Choose the first maximum of this actor's local Q row independently of central diagnostic hints."""
    row=q_lookup(observation,table)
    return local_argmax(row)

def joint_collect(world,positions):
    """Record both actual collectors; a shared pellet is credited once in declared actor order."""
    remaining=world.pellets;collected=[];rewards=[]
    for position in positions:
        remaining,pellet,reward=collect_one(remaining,position)
        collected.append(pellet);rewards.append(reward)
    return remaining,tuple(collected),tuple(rewards)

def candidate_distance(size,start,goal):
    """Return exact orthogonal distance on the declared obstacle-free square."""
    return abs(start[0]-goal[0])+abs(start[1]-goal[1])
