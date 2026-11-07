"""Given exact Q lookup and finite typed expression-tree intake, never a numeric/certificate traversal."""
import math
from .models import QRef,Constant,Sum,Relu
class ExpressionCatalog:
    def __init__(self,values):
        self.order=tuple(uid for uid,_ in values);self.values=dict(values)
        if len(self.order)!=len(self.values)or any(type(uid)is not str or not uid for uid in self.order):raise ValueError('unique global Q UIDs')
        if any(not math.isfinite(v)or abs(v)>1000 for v in self.values.values()):raise ValueError('bounded finite Q values')
    def lookup(self,uid):return self.values.get(uid)
    def validate(self,root):
        seen=set()
        def check(node,depth):
            if depth>16 or node.uid in seen:raise ValueError('finite tree with unique node UIDs')
            seen.add(node.uid)
            if type(node)is QRef:return
            if type(node)is Constant:
                if not math.isfinite(node.value)or abs(node.value)>1000:raise ValueError('bounded constant')
                return
            if type(node)is Relu:check(node.child,depth+1);return
            if type(node)is Sum:
                if not math.isfinite(node.bias)or abs(node.bias)>1000 or len(node.terms)>16:raise ValueError('bounded sum')
                for edge in node.terms:
                    if not math.isfinite(edge.weight)or abs(edge.weight)>10:raise ValueError('bounded edge')
                    check(edge.child,depth+1)
                return
            raise TypeError('declared expression node required')
        check(root,0)
