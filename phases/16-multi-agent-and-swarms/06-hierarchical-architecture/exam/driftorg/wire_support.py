"""GIVEN TSV quoting and complete async sealed-evidence delivery driver."""
import csv,io,json
HEADER=('task','path','node_kind','obligation','status','leaf_id')
def row_bytes(row):
    out=io.StringIO(newline='');csv.writer(out,delimiter='\t',lineterminator='\n').writerow(row);return out.getvalue().encode('utf-8')
def path_text(path):return json.dumps(path,ensure_ascii=False,separators=(',',':'))
async def encode_provenance(source,projection):
    try:
        yield row_bytes(HEADER)
        async for event in source:
            row=projection.leaf_row(event) if event['kind']=='leaf' else projection.branch_row(event)
            yield row_bytes(row)
    finally:await source.aclose()
