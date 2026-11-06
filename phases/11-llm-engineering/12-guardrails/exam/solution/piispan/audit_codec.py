"""GIVEN complete safe AuditSpan object codec and restoration.

The existing validate_audit and AuditSpan constructor own the legal record
contract. This codec preserves every original field and confidence spelling,
while excluding runtime originals; storage and outer manifests remain P2 work.
"""
from .contracts import AuditSpan,validate_audit

def audit_to_records(spans):
    """Validate and encode complete safe AuditSpan records without coercion."""
    values=tuple(spans)
    validate_audit(values)
    return [{"start":s.start,"end":s.end,"kind":s.kind,"fingerprint":s.fingerprint,"confidence_text":s.confidence_text} for s in values]

def audit_from_records(records):
    """Restore safe records with the supplied constructor and audit contract."""
    values=tuple(AuditSpan(**record) for record in records)
    validate_audit(values)
    return values
