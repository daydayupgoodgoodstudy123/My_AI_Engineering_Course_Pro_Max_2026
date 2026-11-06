"""Organize given validator issues; validation itself is already implemented."""

def group_issues(issues):
    """Return {issues:[{code,message}], children:{typed_segment:node}}.

    Paths are tuples of literal string keys or exact integer array indices.
    Never split dots/brackets or stringify indices. Keep all issues at each
    node in input order, including root and parent nodes with children.
    Empty input returns an empty root. Each call and child owns its lists;
    do not mutate input issues. The tree is a Python report, not a JSON wire.
    """
    root = {"issues": [], "children": {}}
    for issue in issues:
        node = root
        for segment in issue.path:
            if segment not in node["children"]:
                node["children"][segment] = {"issues": [], "children": {}}
            node = node["children"][segment]
        node["issues"].append({"code": issue.code, "message": issue.message})
    return root
