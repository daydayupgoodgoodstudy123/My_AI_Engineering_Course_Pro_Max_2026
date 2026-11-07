"""Bounded local JSON-Patch artifacts for complete committed super-steps."""
import copy
def state_patch(event):
    """Transform the exact committed parent state into the complete child state.

    Output bounded add/replace operations in child field insertion order. Encode
    each top-level field as a JSON Pointer segment (~→~0, /→~1). For a declared
    append reducer whose old list is a prefix of the new list, emit each new item
    separately at /field/- in original order, preserving duplicates. Other changed
    fields use replace when present in parent, add when new. No deletes/partial
    worker states: the given driver supplies one validated complete committed pair
    and owns identity/line JSON/pull-through/close. worker_updates are evidence,
    not independently committed intermediate snapshots.
    """
    raise NotImplementedError
