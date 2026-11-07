"""Declared source articles and an independently assembled complete service expectation."""
from .models import SourceKey,SourceSnapshot,Entry,PercentReceipt,SummaryReport
from .support import prompt_digest
def article_fixture(count=32,measurements=14000):
    observations=[];entries=[];receipts=[]
    for i in range(count):
        headline=f'Regional deployment {i} reduced audited error by 4.2%.'
        rows=[f'Observation {j}: batch {i} retained {100+j%37} reviewed records and {j%11} flagged records.' for j in range(measurements)]
        text=headline+' '+ ' '.join(rows)
        source=SourceKey(f'fixture://regional-report/{i}','review-1')
        snapshot=SourceSnapshot(source,text);topic=f'region-{i}';tick=1000+2*i;prompt=f'audit regional deployment {i}'
        observations.append((snapshot,topic,tick,prompt))
        entries.extend((Entry(2*i,'retrieval',topic,text,tick,prompt_digest(prompt),source),Entry(2*i+1,'summarizer',topic,headline,tick+1,prompt_digest(prompt),source)))
        receipts.append(PercentReceipt(2*i+1,'4.2%'))
    return tuple(observations),SummaryReport(tuple(entries),tuple(receipts))
