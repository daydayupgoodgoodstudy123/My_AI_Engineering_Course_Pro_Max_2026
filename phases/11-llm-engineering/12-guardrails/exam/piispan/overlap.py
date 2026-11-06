"""Priority/coverage arbitration for original source intervals, before any scrub."""
from .contracts import validate_spans,AuditSpan,Transcript
from .legacy import apply_spans
from .fingerprint import pii_fingerprint
def resolve_overlaps(text,spans):
    """Choose nonoverlapping candidates by the declared finite greedy policy.

    Rank higher integer priority first, then longer coverage, then lower start,
    lower end, lexical kind and original input ordinal. Accept a candidate iff
    it overlaps no previously accepted interval. Adjacent half-open intervals
    do not overlap; repeated values at distinct intervals remain distinct.
    Return accepted spans in original-text order. This is priority arbitration,
    not maximum-weight interval scheduling or general PII recognition accuracy.
    Primitive bounds/type/confidence checks are supplied. Text and input spans
    remain unchanged. Reuse repaired Part 1 renderer and fingerprint helper.
    """
    raise NotImplementedError
def scrub_overlaps(text,spans,salt):
    """Given integration of the selected original intervals with repaired Part 1."""
    selected=resolve_overlaps(text,spans)
    audits=tuple(AuditSpan(s.start,s.end,s.kind,pii_fingerprint(s.value,salt),s.confidence_text) for s in selected)
    return Transcript(text,apply_spans(text,selected),audits)
