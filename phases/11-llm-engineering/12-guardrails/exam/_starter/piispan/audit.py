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
    raise NotImplementedError
