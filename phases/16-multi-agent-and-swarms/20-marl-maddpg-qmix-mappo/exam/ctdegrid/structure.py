"""Actual nested numeric evaluation and sufficient per-Q derivative-path composition."""
from fractions import Fraction
from .models import QRef,Constant,Sum,Relu,Dependency,ExpressionFinding,ExpressionAudit

def audit_expression(root,catalog):
    """Report every intermediate value and signed path product; failed certificate does not assert an actual value gap."""
    raise NotImplementedError("Complete the declared domain contract")
