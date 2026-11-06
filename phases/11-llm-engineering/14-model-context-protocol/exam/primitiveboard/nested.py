"""Export full paths from explicit local catalogs and their three primitive kinds."""
from .contracts import validate_catalog,scoped_admission,identity
from .surface import descriptor
def export_catalog(root):
    """Visit own entries and children in preorder with each complete catalog path.

    Local CatalogNode hierarchy is a teaching input extension, not federation or
    a multi-server tool routing namespace. Names may repeat under different parents.
    Preserve entry order and kind, including resources keyed by exact URI. The
    correct supplied scoped_admission checks duplicate(kind,identity) only within
    one complete local catalog path. Shape/cycle validation is supplied; do not
    reimplement it. Return each original handler reference with its descriptor.
    """
    raise NotImplementedError
