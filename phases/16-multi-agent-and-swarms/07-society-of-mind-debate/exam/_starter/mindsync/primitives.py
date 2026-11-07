"""Raw numeric record, agreement/truth report and scalar diameter diagnostic."""
from .models import FrozenAgent,RoundRecord
from .numeric_support import diagnostics,render_numeric_record

def make_round_record(index,agents,truth):
    """Retain raw numeric answer/confidence fields; formatting belongs to the renderer."""
    return RoundRecord(index,tuple(FrozenAgent(a.name,f'{a.answer:.2f}',a.confidence) for a in agents),truth)

def consensus_diameter(values):
    """Return exactly the one-dimensional maximum absolute answer gap, zero for<2."""
    return max((abs(values[i]-values[j]) for i in range(len(values)) for j in range(i+1,len(values))),default=0.0)

def report_round(index,agents,truth,tol=0.1):
    """Report the complete numeric vector, display, agreement and independent truth error.

    Correctness is None without a declared truth. Agreement alone is never a
    correctness label. Diameter is a scalar diagnostic, not a weighted solver.
    """
    record=make_round_record(index,agents,truth)
    display=render_numeric_record(record)
    stats=diagnostics(record,tol)
    correct=stats['agreement']==1.0
    return {'record':record,'display':display,'mean':stats['mean'],'agreement':stats['agreement'],'truth_error':stats['truth_error'],'correct':correct,'diameter':consensus_diameter(tuple(a.answer for a in record.agents))}
