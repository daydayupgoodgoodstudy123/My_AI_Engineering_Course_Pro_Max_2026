"""Complete authorized channel classification, finding projection and JSON Text Sequence driver."""
import json
from .models import Entry,VerificationFinding
from .support import ReadOnlyPool,FindingView
def classify_observations(pool_view,finding_view):
    if type(pool_view)is not ReadOnlyPool or type(finding_view)is not FindingView:raise TypeError('declared read capabilities required')
    return tuple(('entry' if entry.supersedes is None else 'correction',entry)for entry in pool_view.read_all())+tuple(('finding',f)for f in finding_view.read_all())
def finding_payload(finding):
    return {'entry_id':finding.entry_id,'source_uri':finding.source.uri,'source_version':finding.source.version,'verdict':finding.verdict,'detail':finding.detail}
def encode_jsonseq(kind,payload):
    return b'\x1e'+json.dumps({'type':kind,'data':payload},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')+b'\n'
async def publish_jsonseq(source,project_entry):
    """Each already-authorized observation is published before pulling another; close on every exit."""
    try:
        async for kind,item in source:
            if kind in ('entry','correction')and type(item)is Entry:payload=project_entry(item,kind)
            elif kind=='finding'and type(item)is VerificationFinding:payload=finding_payload(item)
            else:raise TypeError('authorized typed observation required')
            yield encode_jsonseq(kind,payload)
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
