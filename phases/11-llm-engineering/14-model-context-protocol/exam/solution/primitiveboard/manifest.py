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
    for entry in entries:admit_entry(entry)
    atomic_json(path,{"format":1,"entries":[encode_spec(entry.spec) for entry in entries]})
def load_manifest(path,handlers):
    """Rebind every spec to the supplied safe registry; unknown handler is a load error."""
    value=json.loads(Path(path).read_bytes())
    if value["format"]!=1:raise ValueError("manifest version")
    result=[]
    for item in value["entries"]:
        spec=decode_spec(item);entry=Entry(spec,resolve_handler(spec.handler_name,handlers));admit_entry(entry);result.append(entry)
    return tuple(result)
