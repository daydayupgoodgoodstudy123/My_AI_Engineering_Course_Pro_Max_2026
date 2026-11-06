"""Given typed immutable artifacts; A is input×rank and B is rank×output."""
from dataclasses import dataclass
import math
from .mathops import matrix
@dataclass(frozen=True)
class Adapter:
    path: str
    A: tuple
    B: tuple
    alpha: float
    @property
    def rank(self):return len(self.A[0])
def valid_adapter(adapter):
    A,B=matrix(adapter.A),matrix(adapter.B)
    if not isinstance(adapter.path,str) or not adapter.path or len(A[0])!=len(B):raise ValueError("invalid named adapter shape")
    if type(adapter.alpha) not in (int,float) or not math.isfinite(adapter.alpha):raise ValueError("finite alpha required")
    return Adapter(adapter.path,A,B,float(adapter.alpha))
