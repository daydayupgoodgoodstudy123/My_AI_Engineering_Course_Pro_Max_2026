"""Assemble each nested jury's shared-cause seat model before applying the exact independent-family law."""
from .models import JuryAudit
from . import reliability
def audit_nested_jury(occurrence,catalog):
    """Combine own/child family multiplicities and actual exposures; preserve each nested joint-law report."""
    children=tuple(audit_nested_jury(child,catalog)for child in occurrence.children)
    counts={};reads=list(occurrence.node.reads)
    for family,count in occurrence.node.allocations:counts[family]=counts.get(family,0)+count
    for child in children:
        for family,count in child.family_counts:counts[family]=counts.get(family,0)+count
        reads.extend(child.config.reads)
    config=catalog.config(occurrence.node.uid,tuple(counts.items()),reads)
    kernels=tuple(reliability.family_mass_kernel(family)for family in config.families)
    distribution=reliability.convolve_family_mass(kernels)
    exact=reliability.exact_majority_reliability(config,distribution)
    return JuryAudit(occurrence.path,tuple(counts.items()),config,exact,children)
