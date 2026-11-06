"""Given complete local archive envelope and UTF8 metadata boundary."""
import json,struct
MAGIC=b"LRA1"
def wrap_archive(metadata,payload):
    meta=json.dumps(metadata,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    return struct.pack(">4sII",MAGIC,len(meta),len(payload))+meta+payload
def read_archive(raw):
    if len(raw)<12:raise ValueError("incomplete adapter header")
    magic,nm,np=struct.unpack_from(">4sII",raw)
    if magic!=MAGIC or len(raw)!=12+nm+np:raise ValueError("invalid complete adapter archive")
    return json.loads(raw[12:12+nm].decode("utf-8")),raw[12+nm:]
