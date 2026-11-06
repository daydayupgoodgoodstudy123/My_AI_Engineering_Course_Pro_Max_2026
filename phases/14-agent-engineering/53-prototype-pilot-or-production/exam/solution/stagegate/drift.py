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
    if record.id!=observation.system:raise ValueError('system mismatch')
    issues=[];stage=record.declared_stage
    if (observation.exposed_users or observation.production_data or observation.write_authority) and not record.owner.strip():issues.append('unowned-exposure')
    if stage=='pilot' and observation.exposed_users>record.audience_cap:issues.append('audience-overflow')
    if stage=='pilot' and date.fromisoformat(observation.at)>date.fromisoformat(record.until):issues.append('pilot-expired')
    if stage=='prototype' and observation.production_data:issues.append('prototype-data')
    if stage=='prototype' and observation.write_authority:issues.append('prototype-authority')
    if stage=='production' and not observation.on_call:issues.append('production-on-call')
    markers={m.channel:marker_value(m.value) for m in observation.markers}
    for channel in CHANNELS:
        value=markers.get(channel)
        if value is None:issues.append('missing-marker:'+channel)
        elif value!=stage:issues.append('marker-mismatch:'+channel)
    for control in required_controls(stage):
        if control not in record.controls:issues.append('missing-control:'+control)
    return issues
