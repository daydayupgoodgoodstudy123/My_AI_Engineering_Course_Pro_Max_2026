"""Safe domain payload projection for completed-message NDJSON publication."""
def project_delivery(trace):
    """Project delivered text, typed outcome and safe two-stage audit fields.

    The correct supplied sandwich owns execution and outcome classification; the
    driver owns current request identity, JSON lines, pull-through and closure.
    Publish trace.delivered, never raw_output. Keep each check's category, passed,
    original confidence_text and latency_us in its correct input/output stage;
    exclude details and raw text. Preserve complete original-offset PII audits.
    """
    def checks(results):
        return [{"category":r.category,"passed":r.passed,"confidence_text":r.confidence_text,"latency_us":r.latency_us} for r in results]
    audit={"input_results":checks(trace.report.input_results),"output_results":checks(trace.report.output_results),"pii_spans":[{"start":s.start,"end":s.end,"kind":s.kind,"fingerprint":s.fingerprint,"confidence_text":s.confidence_text} for s in trace.spans]}
    return {"outcome":trace.outcome,"response":trace.delivered,"audit":audit}
