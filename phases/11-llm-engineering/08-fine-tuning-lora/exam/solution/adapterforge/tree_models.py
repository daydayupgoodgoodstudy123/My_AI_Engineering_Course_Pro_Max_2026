"""Given small module graph, separate from torch or autograd."""
from dataclasses import dataclass,field
from .mathops import matrix
@dataclass(eq=False)
class Linear:
    weight: tuple
    bias: tuple
    frozen: bool=False
    def __post_init__(self):
        self.weight=matrix(self.weight);self.bias=tuple(self.bias)
        if len(self.bias)!=len(self.weight[0]):raise ValueError("bias shape")
@dataclass(eq=False)
class Module:
    children: dict=field(default_factory=dict)
@dataclass(eq=False)
class Wrapped:
    base: Linear
    adapter: object
def leaves(root,prefix="",ancestors=()):
    if id(root) in ancestors:raise ValueError("module graph cycle")
    if isinstance(root,Module):
        for name,child in root.children.items():
            path=prefix+"."+name if prefix else name
            yield from leaves(child,path,ancestors+(id(root),))
    elif isinstance(root,(Linear,Wrapped)):yield prefix,root
    else:raise ValueError("unknown module kind")
