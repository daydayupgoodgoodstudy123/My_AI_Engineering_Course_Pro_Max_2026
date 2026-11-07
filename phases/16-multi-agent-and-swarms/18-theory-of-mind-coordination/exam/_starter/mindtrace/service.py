"""Complete replay and source-style simultaneous control settlement; no subject model/predict/own ToM solver."""
from random import Random
from collections import Counter
from . import primitives
from .models import ObservationReceipt,ControlChoice,JointReport,World,ReplayReport
from .support import ObservationLog,observation_view,validate_request,current_events
class ReplayDesk:
    def __init__(self):self.views={}
    def run(self,request):
        validate_request(request);log=ObservationLog(request.initial_observations);receipts=[]
        for event in current_events(request):
            rows=primitives.deliver_visible_event(log,event,request.population)
            seen=tuple(observation_view(log,a.uid,event.subject,event.proposition)for a in request.population if a.uid in event.visible_to)
            receipts.append(ObservationReceipt(event.uid,rows,seen))
        targets=primitives.withdraw_completed_target(request.active_targets,request.completed)
        rng=Random(request.seed);choices=[];view=primitives.available_view(request.world,self.views)
        for a in request.population:
            if a.collected or a.uid in request.completed:continue
            view=primitives.available_view(request.world,self.views)
            if view.boxes:choices.append(ControlChoice(a.uid,rng.choice(view.boxes)))
        counts=Counter(c.box for c in choices);seen=set();taken=[]
        for choice in choices:
            if choice.box not in seen:seen.add(choice.box);taken.append(choice)
        winners={t.subject for t in taken}
        completed=tuple(a.uid for a in request.population if a.collected or a.uid in request.completed or a.uid in winners)
        world=World(request.world.uid,request.world.generation+bool(taken),request.world.available-seen)
        control=JointReport(request.world,view,tuple(choices),tuple(taken),sum(n-1 for n in counts.values()),completed,world,rng.getstate())
        targets=primitives.withdraw_completed_target(targets,completed)
        return ReplayReport(request,tuple(receipts),tuple(log.rows),targets,control)
