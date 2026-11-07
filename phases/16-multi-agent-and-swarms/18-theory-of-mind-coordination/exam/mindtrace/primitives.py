"""Visible observation writers, completed-intent withdrawal and actual generation-bound control view."""
from .models import Observation,AvailableView
from .support import key_for,observation_uid,view_key
def append_observation(log,observer,event):
    """Append the event under the actual observer/subject/proposition binding and preserve all own evidence."""
    row=Observation(observation_uid(event.uid,observer),key_for(event.subject,observer,event.proposition),event.value,event.turn,event.ordinal,event.kind)
    log.append(row)
    return row
def deliver_visible_event(log,event,population):
    """Deliver only to explicitly declared witnesses, preserving population order and absent agents' previous records."""
    return tuple(append_observation(log,a.uid,event)for a in population)
def withdraw_completed_target(targets,completed):
    """Withdraw completed agents' active intentions without deleting their historical observations or beliefs."""
    return tuple(targets)
def available_view(world,cache):
    """Return the canonical immutable current generation inventory shared by a complete joint control turn."""
    key=view_key(world)
    cache[key]=AvailableView(world.uid,world.generation,tuple(sorted(world.available)))
    return cache[key]
