"""Three independent control interpreters over identical corrected primitive interfaces."""
from copy import deepcopy
from .models import step_range
from .control import resolve_target

def replay_static(team,state,order,max_steps=10):
    """Use only external order, ignoring returned handoffs; record complete state and stop reason."""
    raise NotImplementedError

def replay_handoffs(team,state,start,max_steps=10):
    """Follow each returned handoff, preserving explicit done/unknown/budget outcomes."""
    raise NotImplementedError

def replay_selector(team,state,start,selector,max_steps=10):
    """Append before selecting from updated shared state; ignore returned handoff control."""
    raise NotImplementedError
