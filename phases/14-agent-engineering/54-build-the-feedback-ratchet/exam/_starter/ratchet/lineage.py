"""Transitive replacement and retirement reactivation, separately per feedback impact."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class Control:
    id:str
    fingerprint:str
    track:str
    verified:bool=True
    retired:bool=False
    supersedes:tuple[str,...]=()

def graph(controls:list[Control])->dict[str,tuple[str,...]]:
    """Correct supplied general finite-DAG validation, fully iterative. IDs known and
    unique; a replacement edge covers the same fingerprint/track. Historical lineage
    survives retirement/unverified intermediates; coverage edges are explicit input.
    """
    by_id={c.id:c for c in controls}
    if len(by_id)!=len(controls):raise ValueError('duplicate control')
    links={c.id:c.supersedes for c in controls};degree={c.id:0 for c in controls}
    for c in controls:
        for old in c.supersedes:
            if old not in by_id:raise ValueError('unknown predecessor')
            if (c.fingerprint,c.track)!=(by_id[old].fingerprint,by_id[old].track):raise ValueError('replacement identity mismatch')
            degree[old]+=1
    ready=[key for key in degree if degree[key]==0];processed=0
    while ready:
        key=ready.pop();processed+=1
        for old in links[key]:
            degree[old]-=1
            if degree[old]==0:ready.append(old)
    if processed!=len(controls):raise ValueError('replacement cycle')
    return links

def active_controls(controls:list[Control],impacts:list[tuple[str,str]])->dict[tuple[str,str],tuple[str,...]]:
    """Return every requested (fingerprint,track) in request order, even if empty.
    Eligible controls are verified and not retired. Any eligible control suppresses
    ALL its transitive predecessor ancestors through historical lineage (including a
    retired intermediate); effective=eligible minus suppressed. C->B->A: only C when
    all eligible; retiring C revives B but not A; retiring C and B revives A. Unverified
    replacements suppress nothing. Keep product/workbench impacts separately, sort
    control ids per impact, no input mutation. Use correct supplied graph schema.
    """
    raise NotImplementedError
