"""Check a harness description against the lesson's primitives."""
from __future__ import annotations

from dataclasses import dataclass

KINDS = ("runtime", "worker", "trigger", "queue", "store")


@dataclass(frozen=True, order=True)
class Finding:
    path: str  # the component the finding is about; "" is the top runtime
    code: str  # "unresolved", "no_function", "no_policy" or "open_loop"
    detail: str = ""


def check_harness(spec: dict) -> list[Finding]:
    """Check a nested harness description; return the findings sorted by (path, code, detail).

    spec is the top runtime. Every component is a dict with a "kind" from KINDS:

      runtime  "children": {name: component}, runtimes included
      worker   "functions": {name: {"to": [ref, ...]}}, and an authorization "policy"
      trigger  "to": ref, the function or queue it invokes; "on": ref, a store it fires on
      queue    "to": ref, where it delivers
      store    "durable": bool (session persistence is durable; chat history is not)

    A component's path joins the names from the top runtime with "/", and a function's
    path is its worker's path, "/" and its name. Every ref is such a path.

      unresolved   a ref that names nothing (detail: the ref), at the component or
                   function holding it
      no_function  a trigger whose target, followed through any queues, is not a function
      no_policy    a worker without a "policy"
      open_loop    at "": no durable store lies on a cycle. The loop must close on the
                   state file, not on chat history. The edges run from a store to every
                   trigger that fires on it, from a trigger or a queue to its "to", and
                   from a function to each ref in its "to".

    A component of unknown kind raises ValueError.
    """
    nodes: dict[str, dict] = {}

    def walk(node: dict, path: str) -> None:
        kind = node.get("kind")
        if kind not in KINDS:
            raise ValueError(f"{path or 'the top runtime'} has unknown kind {kind!r}")
        if kind in ("trigger", "queue") and not isinstance(node.get("to"), str):
            raise ValueError(f"{path} needs a 'to' ref")
        nodes[path] = node
        if kind == "runtime":
            for name, child in node.get("children", {}).items():
                walk(child, f"{path}/{name}" if path else name)
        elif kind == "worker":
            for name, function in node.get("functions", {}).items():
                nodes[f"{path}/{name}"] = {"kind": "function", "to": list(function.get("to", []))}

    if spec.get("kind") != "runtime":
        raise ValueError("spec must be the top runtime")
    walk(spec, "")
    findings: list[Finding] = []
    edges: dict[str, list[str]] = {path: [] for path in nodes}
    for path, node in nodes.items():
        kind = node["kind"]
        if kind in ("trigger", "queue"):
            refs = [node["to"]]
        elif kind == "function":
            refs = node["to"]
        else:
            refs = []
        for ref in refs:
            if ref in nodes:
                edges[path].append(ref)
            else:
                findings.append(Finding(path, "unresolved", ref))
        if kind == "trigger" and "on" in node:
            if node["on"] in nodes:
                edges[node["on"]].append(path)
            else:
                findings.append(Finding(path, "unresolved", node["on"]))
        if kind == "trigger" and not _reaches_function(path, nodes):
            findings.append(Finding(path, "no_function"))
        if kind == "worker" and "policy" not in node:
            findings.append(Finding(path, "no_policy"))

    durable = [path for path, node in nodes.items() if node["kind"] == "store" and node.get("durable")]
    if not any(_on_cycle(store, edges) for store in durable):
        findings.append(Finding("", "open_loop"))
    return sorted(findings)


def _reaches_function(trigger: str, nodes: dict[str, dict]) -> bool:
    seen: set[str] = set()
    ref = nodes[trigger]["to"]
    while ref in nodes and nodes[ref]["kind"] == "queue" and ref not in seen:
        seen.add(ref)
        ref = nodes[ref]["to"]
    return ref in nodes and nodes[ref]["kind"] == "function"


def _on_cycle(start: str, edges: dict[str, list[str]]) -> bool:
    stack = list(edges[start])
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node == start:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(edges[node])
    return False
