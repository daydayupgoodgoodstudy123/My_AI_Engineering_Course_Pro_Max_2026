"""Given JSON-compatible record codec and exact LF journal boundary."""
import json
def record_bytes(row):return json.dumps(row,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")+b"\n"
def read_records(path):
    if not path.exists():return []
    raw=path.read_bytes()
    if raw and not raw.endswith(b"\n"):raise ValueError("incomplete invocation journal")
    return [json.loads(line.decode("utf-8")) for line in raw.split(b"\n")[:-1]]
