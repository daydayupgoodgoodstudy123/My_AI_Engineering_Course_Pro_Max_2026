"""Complete typed receipt codec for strict JSON values (string-key dict/list/finite scalars)."""
import hashlib,json
from pathlib import Path
from .models import CallResult,Transfer,CallSkipped,CallFailed,Reply
_TYPES={t.__name__:t for t in(CallResult,Transfer,CallSkipped,CallFailed,Reply)}
def encode_receipt(receipt):
    if type(receipt).__name__ not in _TYPES:raise ValueError('typed public receipt')
    fields={name:getattr(receipt,name)for name in receipt.__dataclass_fields__}
    return{'type':type(receipt).__name__,'fields':fields}
def decode_receipt(record):return _TYPES[record['type']](**record['fields'])
def snapshot_path(directory,session):return Path(directory)/(hashlib.sha256(session.encode('utf-8')).hexdigest()+'.json')
def write_snapshot(directory,session,document):
    Path(directory).mkdir(parents=True,exist_ok=True)
    snapshot_path(directory,session).write_text(json.dumps(document,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
def read_snapshot(directory,session):return json.loads(snapshot_path(directory,session).read_text(encoding='utf-8'))
