"""GIVEN real finite population and complete independently constructed report expectation."""
from .models import RoundRecord
from .intake import initial_team

def diagnostic_fixture(count=7000):
    """Every participant is a real report row; setup and expected output are outside timing."""
    rows=tuple((f'agent-{i:05d}',(i%97-48)/8,((i%10)+1)/10) for i in range(count))
    agents=initial_team(rows);mean=sum(i%97-48 for i in range(count))/(8*count);tol=0.1;truth=42.0
    expected={'record':RoundRecord(0,agents,truth),'display':tuple(f'{a.name}: {a.answer:.2f} ({a.confidence:.3f})' for a in agents),'mean':mean,'agreement':sum(abs(a.answer-mean)<=tol for a in agents)/count,'truth_error':abs(mean-truth),'correct':False,'diameter':12.0}
    return (0,agents,truth,tol),expected
