"""Given: complete legal-world binding, moves, exact lookup and local argmax."""
from .models import Observation
ACTIONS=('stay','north','east','south','west')
DELTAS=((0,0),(-1,0),(0,1),(1,0),(0,-1))
def move(size,cell,action):
    dr,dc=DELTAS[ACTIONS.index(action)]
    return max(0,min(size-1,cell[0]+dr)),max(0,min(size-1,cell[1]+dc))
def bind_request(request):
    w=request.world
    if type(w.size) is not int or not 1<=w.size<=128 or type(request.step)is not int or request.step<0:raise ValueError('legal grid and step required')
    if len(w.positions)!=2 or len(request.targets)!=2 or len(request.critic_hints)!=2:raise ValueError('two declared agents required')
    for cell in (*w.positions,*w.pellets,*request.targets):
        if len(cell)!=2 or any(type(x) is not int or not 0<=x<w.size for x in cell):raise ValueError('cell outside empty grid')
    if len(set(w.pellets))!=len(w.pellets) or any(x not in ACTIONS for x in request.critic_hints):raise ValueError('unique pellets and declared actions required')
    return tuple(Observation('agent'+str(i),w.size,w.positions[i],request.targets[i])for i in range(2))
def q_lookup(observation,table):
    """Every declared canonical local observation has a row; ordinary missing keys remain visible."""
    return table[observation]
def local_argmax(row):
    if not row:raise ValueError('nonterminal local Q row required')
    return max(row,key=lambda x:x.value).action

def collect_one(remaining,position):
    """Given one actual collector: stable pellet order, exactly one reward for a matching pellet."""
    if position in remaining:return tuple(x for x in remaining if x!=position),position,1.
    return remaining,None,0.
