"""Cache-safe request preparation; experiment miss execution is a separate Part 3 TODO."""
from dataclasses import replace
from .contracts import Immediate,PreparedMiss
from .routing import get_prompt_record
from .primitives import render_template,cache_key,request_fact
def prepare_safe_request(request,templates,cache,input_guard,output_guard,ledger):
    """Run input safety, scoped prompt/render and output safety even on cache reuse.

    Log exactly one cache/blocked request provenance with zero provider usage.
    A clean model-call miss returns PreparedMiss and is not executed or logged
    here: Part 3 owns branch planning, provider calls and paid-fact attribution.
    Correct cache key/guard policies/formatter are supplied. Keep caller variables.
    """
    cached=cache.get(cache_key(request,request.query))
    if cached is not None:return Immediate(request.request_id,cached,"approved",True)
    input_check=input_guard(request.query)
    if not input_check.passed:
        ledger.append(request_fact(request,"blocked_input"))
        return Immediate(request.request_id,input_check.text,"blocked_input",False)
    prompt=get_prompt_record(templates,request.template,request.version)
    variables=dict(request.variables);variables["query"]=input_check.text
    rendered=render_template(prompt,variables)
    cached=cache.get(cache_key(request,input_check.text))
    if cached is not None:
        output=output_guard(cached);status="approved" if output.passed else "blocked_output"
        ledger.append(request_fact(request,status,True))
        return Immediate(request.request_id,output.text,status,True)
    prepared_request=replace(request,query=input_check.text,variables=variables)
    return PreparedMiss(prepared_request,prompt,rendered)
