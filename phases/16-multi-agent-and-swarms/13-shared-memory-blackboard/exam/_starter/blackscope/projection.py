"""Active correction lineage, exact-version findings and policy-based consumption."""
from .models import EvidenceDecision
def active_provenance_view(entries):
    """Return each same-topic correction lineage's latest append, retaining independent roots.

    Entry IDs are unique and supersedes may name an earlier ID. A cross-topic link
    does not retire another topic: it starts a separate lineage. Output follows append order.
    """
    raise NotImplementedError
def attach_version_findings(entries,findings):
    """Join independent findings by immutable entry ID and full external source snapshot key.

    Any exact DISPUTE wins over exact MATCH; no exact finding is UNVERIFIED.
    These statuses describe fixture evidence, not whether an unverified claim is false.
    """
    raise NotImplementedError
def consumable_entries(entries,findings,policy):
    """An analyst may consume active VERIFIED entries in its declared topics; other roles consume none."""
    raise NotImplementedError
