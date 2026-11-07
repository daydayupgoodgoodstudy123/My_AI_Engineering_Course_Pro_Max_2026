"""Complete local summary orchestration; no active-version or consumption solver."""
from . import intake
from .models import PercentReceipt,SummaryReport
from .support import MessagePool,require_percent_claim
class SummaryDesk:
    def __init__(self,pool=None):self.pool=MessagePool() if pool is None else pool
    def observe(self,snapshot,topic,timestamp_ns,prompt):
        retrieval=intake.append_entry(self.pool,'retrieval',topic,snapshot.text,timestamp_ns,prompt,snapshot.key)
        sentence=intake.first_sentence(snapshot.text)
        claim=require_percent_claim(sentence)
        summary=intake.append_entry(self.pool,'summarizer',topic,sentence,timestamp_ns+1,prompt,snapshot.key)
        return PercentReceipt(summary,claim)
    def observe_many(self,observations):
        receipts=tuple(self.observe(snapshot,topic,tick,prompt)for snapshot,topic,tick,prompt in observations)
        return SummaryReport(self.pool.read_only().read_all(),receipts)
