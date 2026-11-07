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
    before=event.parent.state;after=event.checkpoint.state;operations=[]
    for key,value in after.items():
        if key in before and before[key]==value:continue
        path="/"+key.replace("~","~0").replace("/","~1")
        if event.checkpoint.reducers[key]=="append" and key in before and value[:len(before[key])]==before[key]:
            for item in value[len(before[key]):]:operations.append({"op":"add","path":path+"/-","value":copy.deepcopy(item)})
        else:operations.append({"op":"replace" if key in before else "add","path":path,"value":copy.deepcopy(value)})
    return operations
