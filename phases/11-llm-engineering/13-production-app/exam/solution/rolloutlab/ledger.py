"""Public typed-observation ingestion and exact source-style observability summaries."""
from .contracts import empty_totals,fold_one,copy_summary,validate_observation
class Ledger:
    def __init__(self):self.records=[];self.totals=empty_totals()
    def append(self,row):
        """Receive one actual request/paid-attempt fact and update its complete summary.

        Keep every original record in order. Request and paid-attempt facts have
        separate effects: cache/blocked requests do not invent provider usage.
        """
        validate_observation(row)
        self.records.append(row)
        fold_one(self.totals,row)
    def summary(self):return copy_summary(self.totals)
def replay_observations(ledger,rows):
    """Given public replay path: receive every observed fact and return final evidence.

    This CPU path ingests existing observations, not request generation or provider
    calls. Append and actual final summary/complete original record retention are
    the measured business work; no precomputed totals or dropped observations.
    """
    for row in rows:ledger.append(row)
    return ledger.summary(),tuple(ledger.records)
