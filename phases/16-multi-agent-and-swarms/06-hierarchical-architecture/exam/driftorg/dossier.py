"""Explicit ordered logical-id/member links over supplied typed ZIP primitives."""
from .models import Dossier
from .archive_support import Archive,encode_json,decode_json,encode_leaf,decode_leaf,encode_node,decode_node,member_name

def save_dossier(path,dossier):
    """Write one member per logical leaf/node and an explicit ordered manifest.

    Several summaries may cite the same leaf. The manifest, not ZIP member
    position or recomputed file naming, owns every logical-id/member link.
    """
    raise NotImplementedError

def load_dossier(path):
    """Restore manifest order and all summary references, with explicit link errors.

    Leaf/status/node codecs are complete supplied primitives. A manifest logical
    id must match its member, and each node's cited leaf must exist.
    """
    raise NotImplementedError
