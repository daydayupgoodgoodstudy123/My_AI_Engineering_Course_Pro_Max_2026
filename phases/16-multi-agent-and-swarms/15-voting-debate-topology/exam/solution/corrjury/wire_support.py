"""Complete sealed-trial view, strict-result fields, exact primitives, TSV quoting and async lifecycle."""
import csv,io,json
def canonical_outcome_field(report):return json.dumps(report.family_outcomes,ensure_ascii=False,separators=(',',':'))
def cost_field(value):return str(value)
def frame(fields):
    buffer=io.StringIO(newline='');csv.writer(buffer,delimiter='\t',lineterminator='\n').writerow(fields);return buffer.getvalue()
async def publish_tsv(source,project):
    try:
        async for report in source:yield frame(project(report))
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
