"""Keep observed workflow variants as a prefix tree, including shorter terminal paths."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class Variant:
    id:str
    user:str
    reason:str
    steps:tuple[tuple[str,str],...]

def key(actor:str,action:str)->tuple[str,str]:
    """Correct supplied finite normalization for actor/action identities."""
    return (" ".join(actor.split()).casefold()," ".join(action.split()).casefold())

def variants(observations:list[Variant])->dict:
    """Return a prefix tree with step/count/users/reasons/ends/children at each node.
    Root step is None. count is observations visiting the node, not distinct users.
    users and reasons keep first occurrence; missing/blank reason is 'unknown'. ends
    lists ids ending exactly here in input order, so a path may end before children.
    ids are unique; an empty observed path ends at root. Children sort by descending
    count then normalized actor/action. Never change observations or their step tuples.
    """
    def node(step):return {"step":step,"count":0,"users":[],"reasons":[],"ends":[],"children":{}}
    root=node(None)
    for variant in observations:
        current=root
        for step in (None,*variant.steps):
            if step is not None:
                identity=key(*step);current=current["children"].setdefault(identity,node(identity))
            current["count"]+=1
            if variant.user not in current["users"]:current["users"].append(variant.user)
            reason=variant.reason if variant.reason.strip() else "unknown"
            if reason not in current["reasons"]:current["reasons"].append(reason)
        current["ends"].append(variant.id)
    def freeze(n):
        return {"step":n["step"],"count":n["count"],"users":tuple(n["users"]),"reasons":tuple(n["reasons"]),"ends":tuple(n["ends"]),"children":[freeze(c) for c in sorted(n["children"].values(),key=lambda c:(-c["count"],c["step"]))]}
    return freeze(root)
