"""Actual nested numeric evaluation and sufficient per-Q derivative-path composition."""
from fractions import Fraction
from .models import QRef,Constant,Sum,Relu,Dependency,ExpressionFinding,ExpressionAudit

def audit_expression(root,catalog):
    """Report every intermediate value and signed path product; failed certificate does not assert an actual value gap."""
    catalog.validate(root)
    def visit(node,path):
        path=path+(node.uid,)
        if type(node)is QRef:
            value=catalog.lookup(node.q_uid)
            if value is None:return ExpressionAudit(node.uid,None,(),(ExpressionFinding('unknown-Q',path,node.q_uid),),())
            return ExpressionAudit(node.uid,value,(Dependency(node.q_uid,(Fraction(1),),True),),(),())
        if type(node)is Constant:return ExpressionAudit(node.uid,node.value,(),(),())
        if type(node)is Relu:
            child=visit(node.child,path)
            return ExpressionAudit(node.uid,None if child.value is None else max(0.,child.value),child.dependencies,child.findings,(child,))
        children=tuple(visit(edge.child,path)for edge in node.terms);products={}
        for edge,child in zip(node.terms,children):
            for dep in child.dependencies:products.setdefault(dep.q_uid,[]).extend(Fraction(edge.weight)*c for c in dep.coefficients)
        dependencies=tuple(Dependency(uid,tuple(products[uid]),all(c>=0 for c in products[uid]))for uid in catalog.order if uid in products)
        findings=tuple(f for child in children for f in child.findings)
        value=None if any(child.value is None for child in children)else node.bias+sum(edge.weight*child.value for edge,child in zip(node.terms,children))
        return ExpressionAudit(node.uid,value,dependencies,findings,children)
    return visit(root,())
