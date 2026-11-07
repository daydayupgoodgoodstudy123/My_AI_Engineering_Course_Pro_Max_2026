"""Given append/length frame I/O; candidate owns envelope and content records."""
import json,struct
from pathlib import Path
def append_record(path,record):
    payload=json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8")
    with Path(path).open("ab") as output:output.write(struct.pack(">Q",len(payload))+payload)
def read_records(path):
    path=Path(path)
    if not path.exists():return []
    raw=path.read_bytes();i=0;rows=[]
    while i<len(raw):
        if len(raw)-i<8:raise ValueError("truncated local journal")
        length=struct.unpack_from(">Q",raw,i)[0];i+=8
        if len(raw)-i<length:raise ValueError("truncated local journal")
        rows.append(json.loads(raw[i:i+length]));i+=length
    return rows
