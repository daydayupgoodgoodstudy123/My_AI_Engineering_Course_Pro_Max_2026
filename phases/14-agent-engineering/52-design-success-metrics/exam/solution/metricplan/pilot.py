"""Fixed replay batches plus the entire pilot's write guardrail; private TAP-style text."""
from __future__ import annotations
from collections.abc import AsyncIterable,AsyncIterator
from .replays import Replay
from .decision import DecisionPlan,Decision,decide

def tap_rows(result:Decision,window:int,number:int)->list[str]:
    """Correct supplied wire helper: three lines per window, global consecutive ids.
    The exact private text is specified here, with a status and value comment. This
    exercise does not require external TAP protocol knowledge.
    """
    fields=(('correct_service_rate',result.accuracy),('median_seconds',result.median_seconds),('production_writes',result.writes))
    return [('ok' if result.status=='pass' else 'not ok')+f' {number+i} - {name} [{window}] # {result.status} {value}\n' for i,(name,value) in enumerate(fields)]

async def pilot(plan:DecisionPlan,source:AsyncIterable[Replay],workload:float=0)->AsyncIterator[str]:
    """Process fixed, disjoint batches of plan.batch_size included population rows.
    Any production write in any pilot record (also excluded/wrong-population) emits
    'Bail out! production write\n' immediately, before successful metric lines, then
    stops without a future pull. At each complete batch, emit all three tap_rows in
    helper order before reading again; reset the batch, not a sliding recent-N window.
    At EOF emit an incomplete batch only if >=1 included target-population rows remain,
    marked ambiguous; no empty window. Closing at any yield cannot prefetch.
    """
    rows=[];count=0;window=1;number=1
    async for row in source:
        if row.writes:yield 'Bail out! production write\n';return
        rows.append(row)
        if row.included and row.population==plan.population:count+=1
        if count==plan.batch_size:
            for line in tap_rows(decide(plan,plan,rows,workload),window,number):yield line
            rows=[];count=0;window+=1;number+=3
    if count:
        for line in tap_rows(decide(plan,plan,rows,workload),window,number):yield line
