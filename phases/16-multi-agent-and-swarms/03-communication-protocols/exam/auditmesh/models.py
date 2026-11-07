"""GIVEN local shapes and ownership-independent message validation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Observation:
    audit: dict
    reply: dict | None

@dataclass(frozen=True)
class PublicPolicy:
    tool_input: bool = False
    tool_output: bool = False

def validate_parts(parts):
    """Check the finite tagged shape; URLs and media types remain opaque strings."""
    if not isinstance(parts,list):raise ValueError('local message parts')
    for part in parts:
        if not isinstance(part,dict):raise ValueError('local message part')
        kind=part.get('kind')
        if kind=='text':
            if not isinstance(part.get('text'),str):raise ValueError('local text part')
        elif kind=='data':
            if 'data' not in part or not isinstance(part.get('media_type'),str):raise ValueError('local data part')
        elif kind=='file':
            if not all(isinstance(part.get(key),str) for key in ('name','url','media_type')):raise ValueError('local file part')
        else:raise ValueError('local part tag')
