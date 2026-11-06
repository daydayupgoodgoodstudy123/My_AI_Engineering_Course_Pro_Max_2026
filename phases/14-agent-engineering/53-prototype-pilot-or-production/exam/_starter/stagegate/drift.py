"""Observe boundary drift without upgrading an environment from its deployment facts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .stages import Registration,Marker,CHANNELS,required_controls
@dataclass(frozen=True)
class Observation:
    system:str
    at:str
    exposed_users:int
    production_data:bool
    write_authority:bool
    on_call:bool
    markers:tuple[Marker,...]

def marker_value(value:str|None)->str|None:
    """Correct supplied finite marker normalization; absent/blank/unknown is missing."""
    if value is None:return None
    value=value.strip().casefold()
    return value if value in ('prototype','pilot','production') else None

def drift(record:Registration,observation:Observation)->list[str]:
    """Same system id, valid ISO dates; exposed_users is the cumulative distinct
    admitted/exposed pilot audience, never reduced by session departures. It is not
    audiences() active-session telemetry. Four channels are unique.
    Return all current issues in this order: unowned-exposure (any users/data/write,
    no owner), pilot audience-overflow (>cap), pilot-expired (after inclusive until),
    prototype-data, prototype-authority, production-on-call, then missing-marker or
    marker-mismatch for CHANNELS in order, then missing-control in required order.
    A pilot may legitimately use production data. Only the declaration determines its
    control contract; observed facts/markers do not automatically relabel the stage.
    """
    raise NotImplementedError
