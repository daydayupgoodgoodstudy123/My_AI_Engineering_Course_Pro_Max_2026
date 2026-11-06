"""Given domain JSON/dbm keys and correct CSV encoding primitive."""
from dataclasses import asdict
import csv
import io
import json

def dbkey(kind,*identity):return json.dumps([kind,*identity],ensure_ascii=False,separators=(",",":")).encode("utf-8")
def encode(value):return json.dumps(value,ensure_ascii=False,separators=(",",":")).encode("utf-8")
def decode(value):return json.loads(value.decode("utf-8"))
def record(row):return asdict(row)
CSV_FIELDS=("query_id","doc_id","initial_rank","rerank_score","parent_id","source_label")
def csv_chunk(rows,header=False):
    output=io.StringIO(newline="")
    writer=csv.DictWriter(output,fieldnames=CSV_FIELDS,lineterminator="\r\n")
    if header:writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
