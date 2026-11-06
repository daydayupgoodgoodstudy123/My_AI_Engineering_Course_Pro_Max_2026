"""Online framing workshop: show issue changes without replaying unchanged content."""
from __future__ import annotations
import copy
from dataclasses import dataclass
from collections.abc import AsyncIterator
from .frame import Frame,Compatibility,validate
@dataclass(frozen=True)
class Edit:
    field:str
    value:object

def _delta(before:list[str],after:list[str])->list[str]:
    """Correct supplied complete issue-set comparison: removals, then additions,
    each sorted. Quiet edits have no lines. The candidate need not redo deduplication.
    """
    return ["- "+s for s in sorted(set(before)-set(after))]+["+ "+s for s in sorted(set(after)-set(before))]

async def workshop(frame:Frame,edits:AsyncIterator[Edit],compatibility:Compatibility,aliases:dict)->AsyncIterator[str]:
    """Apply edits to a private deep copy. Supported fields are Frame fields; unknown
    fields raise ValueError. Value types match their fields. Every consumed edit counts
    towards N, including quiet edits. If _delta reports changes, yield one complete
    private diff block '@@ edit N @@\n' plus its lines and final newline before pulling
    the next edit. Initial issues are baseline, not an initial block. Input stays intact.
    """
    raise NotImplementedError
