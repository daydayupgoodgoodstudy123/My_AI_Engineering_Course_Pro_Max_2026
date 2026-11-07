"""Real simultaneous token choices and independent full replay expectation outside timing."""
from random import Random
from collections import Counter
from .models import *
def replay_fixture(agents_count=800,boxes_count=6000):
    agents=tuple(Agent(('agent',str(i)),'Agent '+str(i))for i in range(agents_count));boxes=tuple(sorted('box-'+str(i)for i in range(boxes_count)));world=World('fixture-world',0,frozenset(boxes));event=VisibleEvent('approach',agents[1].uid,'target',boxes[0],1,0,'action',(agents[0].uid,));request=ReplayRequest(agents,(event,),(),(),(),world,921,1)
    row=Observation('approach:["agent", "0"]',BeliefKey(agents[0].uid,agents[1].uid,'target'),boxes[0],1,0,'action');rng=Random(921);choices=tuple(ControlChoice(a.uid,rng.choice(boxes))for a in agents);seen=set();taken=[]
    for c in choices:
        if c.box not in seen:seen.add(c.box);taken.append(c)
    completed=tuple(a.uid for a in agents if any(c.subject==a.uid for c in taken));counts=Counter(c.box for c in choices)
    control=JointReport(world,AvailableView(world.uid,0,boxes),choices,tuple(taken),sum(n-1 for n in counts.values()),completed,World(world.uid,1,world.available-seen),rng.getstate())
    return request,ReplayReport(request,(ObservationReceipt('approach',(row,),(row,)),),(row,),(),control)
