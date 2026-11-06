"""Targeted adapter injection and physical-parameter reporting on a module graph."""
from .models import Adapter,valid_adapter
from .tree_models import Linear,Wrapped,Module,leaves
from .service import AdapterService
def inject(root,targets,rank,alpha,factory):
    """Select exact leaf names or full paths. One physical leaf gets one wrapper across all aliases.

    All base Linear objects become frozen. A shared physical Linear is selected when any
    alias matches; its wrapper is installed at every alias. Return selected alias paths
    in traversal order. Existing wrappers are not revisited or reinitialized.
    """
    raise NotImplementedError
def parameter_report(root):
    """Count physical base/adapter parameters once while listing all wrapper alias paths."""
    raise NotImplementedError
def merge_tree(root):
    """Merge each physical wrapper once, replace every alias and preserve shared base identity."""
    raise NotImplementedError
