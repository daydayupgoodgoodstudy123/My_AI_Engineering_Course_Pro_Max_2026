"""Local observation, decision, joint collection and obstacle-free distance contracts."""
from collections import deque
from .models import Observation
from .world_support import q_lookup,local_argmax,collect_one

def encode_local_observation(raw):
    """Preserve the declared actor's row/column coordinates and target identity."""
    return Observation(raw.agent_uid,raw.size,(raw.cell[1],raw.cell[0]),raw.target)

def local_actor(observation,table,critic_hint):
    """Choose the first maximum of this actor's local Q row independently of central diagnostic hints."""
    row=q_lookup(observation,table)
    return critic_hint

def joint_collect(world,positions):
    """Record both actual collectors; a shared pellet is credited once in declared actor order."""
    remaining=world.pellets;collected=[];rewards=[]
    for position in positions:
        remaining,pellet,reward=collect_one(remaining,position)
        collected.append(pellet);rewards.append(reward)
        if pellet is not None:break
    while len(collected)<2:collected.append(None);rewards.append(0.)
    return remaining,tuple(collected),tuple(rewards)

def candidate_distance(size,start,goal):
    """Return exact orthogonal distance on the declared obstacle-free square."""
    queue=deque([(start,0)]);seen={start}
    while queue:
        cell,d=queue.popleft()
        if cell==goal:return d
        for dr,dc in ((-1,0),(0,1),(1,0),(0,-1)):
            nxt=cell[0]+dr,cell[1]+dc
            if 0<=nxt[0]<size and 0<=nxt[1]<size and nxt not in seen:seen.add(nxt);queue.append((nxt,d+1))
    raise ValueError('unreachable empty-grid goal')
