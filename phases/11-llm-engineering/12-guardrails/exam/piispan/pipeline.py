"""Given source-style guardrail sandwich, actual async pull-through/close and JSON line codec."""
import json
from .contracts import GuardrailReport,Trace,BLOCKED_INPUT,BLOCKED_OUTPUT,block_reason
from .legacy import GuardService
from .publish import project_delivery
class Sandwich:
    def __init__(self,recognizers,salt,input_checks,output_checks):
        self.service=GuardService(recognizers,salt);self.input_checks=input_checks;self.output_checks=output_checks
    def process(self,message):
        inputs=tuple(self.input_checks(message.prompt));failures=[x for x in inputs if not x.passed]
        if failures:
            report=GuardrailReport(inputs,(),True,block_reason("Input",failures[0]))
            return Trace(report,False,False,BLOCKED_INPUT,None,(),"blocked_input")
        raw=message.replay(message.prompt)
        if type(raw) is not str:raise ValueError("replay response")
        inspected=self.service.inspect(raw,tuple(self.output_checks(message.prompt,raw)))
        hard=[x for x in inspected.results if not x.passed and x.category!="pii_scrubbing"]
        blocked=inspected.blocked
        report=GuardrailReport(inputs,inspected.results,blocked,block_reason("Output",hard[0]) if hard else "")
        scrubbed=not blocked and inspected.transcript.redacted!=raw
        outcome="blocked_output" if blocked else "scrubbed" if scrubbed else "approved"
        return Trace(report,True,scrubbed,inspected.delivered,raw,inspected.transcript.spans,outcome)
async def publish(messages,sandwich):
    """Given one-complete-message driver; owner identity, NDJSON and closure are supplied."""
    iterator=messages.__aiter__()
    try:
        async for message in iterator:
            trace=sandwich.process(message)
            record={"request_id":message.request_id}
            record.update(project_delivery(trace))
            yield json.dumps(record,ensure_ascii=False,separators=(",",":"))+"\n"
    finally:
        close=getattr(iterator,"aclose",None)
        if close is not None:await close()
