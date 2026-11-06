"""Local JSON surface manifests use only safe named local handler references."""
import json
from pathlib import Path
from .contracts import Entry,encode_spec,decode_spec,resolve_handler,atomic_json,admit_entry
def save_manifest(path,entries):
    """Atomically save every ordered primitive spec with its original handler name.

    Correct complete spec codec and atomic JSON writer are supplied. No callable
    serialization, import-by-string or executable deserialization is permitted.
    Preserve URI, descriptions, schema, prompt argument order and kind identity.
    """
    raise NotImplementedError
def load_manifest(path,handlers):
    """Rebind every spec to the supplied safe registry; unknown handler is a load error."""
    raise NotImplementedError
