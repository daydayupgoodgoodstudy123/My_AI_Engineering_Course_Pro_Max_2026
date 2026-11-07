"""Resolve one target value; no complete interpreter is provided here."""
from .models import Target

def resolve_target(target,team):
    """Distinguish known successor, explicit done, selector None and an unknown target."""
    if target is None:return Target('selector-stop',None)
    if target=='done':return Target('done',None)
    if target in team:return Target('next',target)
    return Target('done',None)
