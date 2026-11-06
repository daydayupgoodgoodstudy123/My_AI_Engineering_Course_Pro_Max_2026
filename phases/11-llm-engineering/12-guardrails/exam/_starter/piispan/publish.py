"""Safe domain payload projection for completed-message NDJSON publication."""
def project_delivery(trace):
    """Project delivered text, typed outcome and safe two-stage audit fields.

    The correct supplied sandwich owns execution and outcome classification; the
    driver owns current request identity, JSON lines, pull-through and closure.
    Publish trace.delivered, never raw_output. Keep each check's category, passed,
    original confidence_text and latency_us in its correct input/output stage;
    exclude details and raw text. Preserve complete original-offset PII audits.
    """
    raise NotImplementedError
