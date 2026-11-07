"""Nested primitive ownership adapter; explicit stores are shared object references."""

def flatten_composition(root,stores,default_store,default_scheduler):
    """Bind leaves to scoped names and inherited store/scheduler; report path-local cycles.

    group nodes contain kind/name/children and optional store/scheduler overrides.
    agent nodes contain kind/name/agent. Store values name entries in the supplied
    registry; each leaf retains that exact SharedState object. A reused acyclic
    subtree is allowed under distinct scoped paths. The composition is not run.
    """
    raise NotImplementedError
