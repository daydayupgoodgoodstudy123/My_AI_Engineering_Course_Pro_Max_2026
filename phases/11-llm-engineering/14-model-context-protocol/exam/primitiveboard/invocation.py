"""Given per-entry invocation, primitive output checks and result projector integration."""
from .contracts import validate_output
from .surface import project_result
def invoke_entry(entry,arguments):
    output=entry.handler() if entry.spec.kind=="resource" else entry.handler(**arguments)
    validate_output(entry,output)
    return project_result(entry,output)
