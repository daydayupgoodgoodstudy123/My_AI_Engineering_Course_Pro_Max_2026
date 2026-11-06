"""Adapter loading, full forward evaluation and idempotent merge."""
from .models import Adapter
from .mathops import matrix,matmul,vecmat
def load_record(record):
    """Load a named row-vector adapter without changing its factor orientation."""
    return Adapter(record["path"],matrix(record["B"]),matrix(record["A"]),record["alpha"])
def adapter_scale(adapter):
    """Return the course alpha/rank scale."""
    return adapter.alpha
def lora_forward(vector,base,bias,adapter):
    """Evaluate base plus the scaled adapter residual for this vector."""
    delta=matmul(adapter.A,adapter.B)
    residual=vecmat(vector,delta)
    if len(residual)!=len(bias):raise ValueError("adapter output dimension disagrees with base")
    original=vecmat(vector,base);scale=adapter_scale(adapter)
    return tuple(y+b+scale*d for y,b,d in zip(original,bias,residual))
class AdapterService:
    def __init__(self,base,bias,record):
        self.base=matrix(base);self.bias=tuple(bias);self.adapter=load_record(record);self.merged=False
        if len(self.bias)!=len(self.base[0]):raise ValueError("base bias shape")
    def forward(self,vector):
        """Return a complete base-plus-adapter output, including base bias."""
        if self.merged:return tuple(v+b for v,b in zip(vecmat(vector,self.base),self.bias))
        return lora_forward(vector,self.base,self.bias,self.adapter)
    def merge(self):
        """Merge this adapter into its frozen base at most once."""
        delta=matmul(self.adapter.A,self.adapter.B);scale=adapter_scale(self.adapter)
        self.base=tuple(tuple(w+scale*d for w,d in zip(row,change)) for row,change in zip(self.base,delta))
        self.merged=True
