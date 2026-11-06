"""Given correct rendering, scoped cache identity and supplied guard interfaces."""
from .contracts import RequestObservation
def render_template(record,variables):return record.template.format_map(variables)
def cache_key(request,effective):return (request.user,request.template,request.version,effective)
def request_fact(request,status,cache_hit=False):
    return RequestObservation(request.request_id,request.user,request.template,request.version,status,cache_hit)
