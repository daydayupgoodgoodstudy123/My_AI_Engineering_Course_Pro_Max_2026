"""Validate finite source GuardrailReport stage evidence and aggregate request outcomes."""
from .contracts import validate_report_shape,block_reason
def audit_sandwich(traces):
    """Validate the source input -> model -> output sandwich and count requests once.

    An input failure requires blocked=True, no model/output evidence and no safe
    scrub event. Otherwise the model executes and exactly one pii_scrubbing
    output result exists. A failed non-scrub output check hard-blocks; a scrub
    failure alone is a permitted sanitized delivery. block_reason identifies
    the first failing hard check in source order. Only a passed sanitized
    delivery is a pii_scrubbed event. Reject contradictory execution evidence.
    Return request counts plus per-stage original check paths and first-block
    category counts, preserving input order and every failed detector path.
    Primitive records are supplied; do not rerun detectors, scrub text or invoke
    model callbacks. There is no arbitrary execution tree or policy inheritance.
    """
    totals={"requests":0,"passed":0,"blocked_input":0,"blocked_output":0,"pii_scrubbed":0};categories={};evidence=[]
    for ordinal,trace in enumerate(traces):
        validate_report_shape(trace);report=trace.report
        input_failed=[(i,r) for i,r in enumerate(report.input_results) if not r.passed]
        hard_output=[(i,r) for i,r in enumerate(report.output_results) if not r.passed and r.category!="pii_scrubbing"]
        pii=[r for r in report.output_results if r.category=="pii_scrubbing"]
        if input_failed:
            stage="input";first=input_failed[0][1]
            if not report.blocked or trace.model_called or report.output_results or trace.pii_scrubbed:raise ValueError("input-block evidence")
        else:
            if not trace.model_called or len(pii)!=1:raise ValueError("output-stage evidence")
            if hard_output:
                stage="output";first=hard_output[0][1]
                if not report.blocked or trace.pii_scrubbed:raise ValueError("output-block evidence")
            else:
                stage="passed";first=None
                if report.blocked or trace.pii_scrubbed!=(not pii[0].passed):raise ValueError("passed/scrub evidence")
        expected="" if first is None else block_reason("Input" if stage=="input" else "Output",first)
        if report.block_reason!=expected:raise ValueError("block reason evidence")
        totals["requests"]+=1
        totals["passed" if stage=="passed" else "blocked_"+stage]+=1
        totals["pii_scrubbed"]+=int(trace.pii_scrubbed)
        if first is not None:categories[first.category]=categories.get(first.category,0)+1
        paths=tuple((ordinal,name,index,result.category) for name,results in (("input_results",report.input_results),("output_results",report.output_results)) for index,result in enumerate(results) if not result.passed)
        evidence.append({"stage":stage,"report":report,"failed_paths":paths})
    return {"totals":totals,"block_categories":categories,"evidence":evidence}
