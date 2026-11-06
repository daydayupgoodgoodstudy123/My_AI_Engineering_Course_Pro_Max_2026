"""Content-addressed frame revisions preserve each decision and its parent."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from dataclasses import asdict,dataclass
from .frame import Frame,Constraint
@dataclass(frozen=True)
class Revision:
    digest:str
    parent:str|None
    frame:Frame
class Revisions:
    """Each object is JSON whose full UTF-8 bytes hash to its filename. Parent links
    are part of identity. Saving equal frame+parent returns the same digest. Frame list
    order and all strings stay unchanged. Reading returns independent frame objects.
    """
    def __init__(self,root:str): self.root=Path(root)
    def save(self,frame:Frame,parent:str|None=None)->str:
        """Save a revision; an unknown parent raises KeyError before any write."""
        if parent is not None: self.load(parent)
        raw={"parent":parent,"frame":asdict(frame)}
        data=json.dumps(raw,ensure_ascii=False,sort_keys=True).encode("utf-8")
        digest=hashlib.sha256(data).hexdigest()
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/(digest+".json")).write_bytes(data)
        return digest
    def load(self,digest:str)->Revision:
        """Load one revision; unknown digests raise KeyError."""
        try: raw=json.loads((self.root/(digest+".json")).read_bytes())
        except FileNotFoundError: raise KeyError(digest) from None
        data=raw["frame"];data["constraints"]=[Constraint(**c) for c in data["constraints"]]
        return Revision(digest,raw["parent"],Frame(**data))
    def history(self,digest:str)->list[Revision]:
        """Walk from this revision back through every parent, newest first."""
        result=[]
        while digest is not None:
            revision=self.load(digest);result.append(revision);digest=revision.parent
        return result
