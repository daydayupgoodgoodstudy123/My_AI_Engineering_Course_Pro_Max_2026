"""Inherited topic scope, pool visibility and actual per-group completed work."""
def inspect_deployment(root,completions):
    """Apply ancestor topic intersections, keep sibling private pools out, and total actual completions.

    GroupCatalog supplies full worker/pool identity, ancestor tests and complete
    subtree membership. A worker's effective topics are its own subscriptions
    intersected with every declared group restriction. Own pools are visible;
    only shared ancestor pools may be inherited. Running/queued work is not done.
    """
    raise NotImplementedError
