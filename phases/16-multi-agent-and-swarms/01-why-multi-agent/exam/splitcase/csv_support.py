"""Given CSV framing and finite stage validation; not a provider protocol."""
import csv,io,json
from .models import usage_value,boundary_value,Boundary,count
COLUMNS=("run","stage","role","input_tokens","output_tokens","lost_fact_ids","status")
def csv_piece(row=None):
    output=io.StringIO(newline="");writer=csv.DictWriter(output,fieldnames=COLUMNS,lineterminator="\r\n")
    if row is None:writer.writeheader()
    else:writer.writerow(row)
    return output.getvalue()
def stage_value(stage):
    count(stage.stage)
    if stage.status not in ("ok","failed"):raise ValueError("stage status")
    if stage.usage is not None:
        usage_value(stage.usage)
        if stage.usage.role!=stage.role:raise ValueError("usage belongs to another role")
    boundary_value(Boundary("stage",stage.role,stage.before,stage.forwarded,stage.required))
    return stage
def usage_fields(usage):
    if usage is None:return "",""
    return ("" if usage.input_tokens is None else usage.input_tokens,"" if usage.output_tokens is None else usage.output_tokens)
def fact_ids_text(ids):return json.dumps(list(ids),ensure_ascii=False,separators=(",",":"))
