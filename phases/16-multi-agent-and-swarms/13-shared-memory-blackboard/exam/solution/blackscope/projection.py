"""Active correction lineage, exact-version findings and policy-based consumption."""
from .models import EvidenceDecision
def active_provenance_view(entries):
    """Return each same-topic correction lineage's latest append, retaining independent roots.

    Entry IDs are unique and supersedes may name an earlier ID. A cross-topic link
    does not retire another topic: it starts a separate lineage. Output follows append order.
    """
    by_id={};roots={};latest={}
    for entry in entries:
        parent=by_id.get(entry.supersedes)
        root=roots[parent.entry_id] if parent is not None and parent.topic==entry.topic else entry.entry_id
        by_id[entry.entry_id]=entry;roots[entry.entry_id]=root;latest[root]=entry.entry_id
    active=set(latest.values())
    return tuple(entry for entry in entries if entry.entry_id in active)
def attach_version_findings(entries,findings):
    """Join independent findings by immutable entry ID and full external source snapshot key.

    Any exact DISPUTE wins over exact MATCH; no exact finding is UNVERIFIED.
    These statuses describe fixture evidence, not whether an unverified claim is false.
    """
    decisions=[]
    for entry in entries:
        exact=tuple(f for f in findings if f.entry_id==entry.entry_id and entry.source is not None and f.source==entry.source)
        status='DISPUTED' if any(f.verdict=='DISPUTE'for f in exact)else 'VERIFIED' if any(f.verdict=='MATCH'for f in exact)else 'UNVERIFIED'
        decisions.append(EvidenceDecision(entry,status,exact))
    return tuple(decisions)
def consumable_entries(entries,findings,policy):
    """An analyst may consume active VERIFIED entries in its declared topics; other roles consume none."""
    active=active_provenance_view(entries)
    if policy.role!='analyst':return ()
    return tuple(decision for decision in attach_version_findings(active,findings)if decision.entry.topic in policy.topics and decision.status=='VERIFIED')
