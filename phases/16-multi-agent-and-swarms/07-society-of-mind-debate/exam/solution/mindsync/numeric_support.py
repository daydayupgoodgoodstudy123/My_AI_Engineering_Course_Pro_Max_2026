"""GIVEN unweighted diagnostics and final display; no confidence-weighted solver."""
from fractions import Fraction

def numeric_mean(values):
    """Exact binary-rational unweighted accumulation, rounded once to binary64."""
    return float(sum((Fraction.from_float(value) for value in values),Fraction())/len(values))

def diagnostics(record,tol):
    values=tuple(a.answer for a in record.agents);mean=numeric_mean(values)
    agreement=sum(abs(value-mean)<=tol for value in values)/len(values)
    error=None if record.truth is None else abs(mean-record.truth)
    return {'mean':mean,'agreement':agreement,'truth_error':error}

def render_numeric_record(record):
    """Format numeric record fields only at the final presentation boundary."""
    return tuple(f'{agent.name}: {agent.answer:.2f} ({agent.confidence:.3f})' for agent in record.agents)
