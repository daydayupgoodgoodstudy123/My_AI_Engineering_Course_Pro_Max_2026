"""Exact subset marginals, fresh complete permutations and completed-block allocation reports."""
from fractions import Fraction
from itertools import combinations
from math import factorial
from .models import Marginal,AllocationBlock,AllocationReport
from .allocation_support import bind_oracle,validate_blocks
from .primitives import efficiency_report

def shapley_exact(game,oracle):
    """Compute each player's exact weighted subset marginals, retaining every signed evidence term."""
    raise NotImplementedError('Complete the declared domain contract')

def shapley_sampled(game,oracle,samples,rng):
    """Sample fresh complete seeded permutations; store marginal totals and actual completed traces."""
    raise NotImplementedError('Complete the declared domain contract')

def allocation_report(game,oracle,blocks):
    """Combine actual completed sample totals, label approximation/partial work, and use the supplied efficiency helper."""
    raise NotImplementedError('Complete the declared domain contract')
