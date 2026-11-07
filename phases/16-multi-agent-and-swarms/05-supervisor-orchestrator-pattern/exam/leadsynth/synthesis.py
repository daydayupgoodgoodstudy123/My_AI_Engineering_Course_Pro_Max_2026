"""Explicit finite claim reconciliation, not free-text semantic inference."""
def partition_claims(artifacts):
    """Return accepted and quarantined occurrences with original worker attribution.

    A claim is in scope only when its topic belongs to that artifact's scope.
    Claims from cut workers are quarantined. Preserve occurrence order.
    """
    raise NotImplementedError

def merge_claim_evidence(accepted):
    """Group by claim and exact value, union original sources, preserve contradictions.

    First-seen order governs claims, alternatives and provenance. Two distinct
    source ids support one value; zero/one is unverified. Multiple values remain
    conflicting regardless of support count. Repeated source ids are not votes.
    """
    raise NotImplementedError

def request_targeted_followup(report,budgets):
    """One narrow request per conflicting claim with positive remaining budget.

    The request names only that conflict, its original topics, worker ids and
    alternatives. Return remaining budget without mutating the input mapping.
    Zero budget leaves the conflict visible and yields no request.
    """
    raise NotImplementedError
