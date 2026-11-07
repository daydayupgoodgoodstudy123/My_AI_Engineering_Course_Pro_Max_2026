"""Independent local-call fixture accounting; Python characters are declared units."""
from .models import Usage,count,usage_value

def record_call_usage(request):
    """Record input floor((len(system)+len(user))/4), fixture output and tool calls.

    This deterministic estimate is not a tokenizer, UTF8 byte count or JS UTF16
    measurement. Preserve each independent call's id and role.
    """
    count(request.call_id);count(request.output_tokens);count(request.tool_calls)
    input_tokens=(len(request.system)+len(request.user))//4
    return Usage(request.call_id,request.role,input_tokens,request.output_tokens,request.tool_calls)

def sum_branch_usage(usages):
    """Sum all measured independent branches, including repeated calls to one role."""
    input_tokens=output_tokens=tool_calls=0
    for usage in usages:
        usage_value(usage,measured=True)
        input_tokens+=usage.input_tokens;output_tokens+=usage.output_tokens;tool_calls+=usage.tool_calls
    return {"input_tokens":input_tokens,"output_tokens":output_tokens,"tool_calls":tool_calls,"total_tokens":input_tokens+output_tokens}
