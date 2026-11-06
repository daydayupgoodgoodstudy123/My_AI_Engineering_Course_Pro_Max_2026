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
    raise NotImplementedError
