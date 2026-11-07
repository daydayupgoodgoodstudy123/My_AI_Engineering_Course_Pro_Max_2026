"""Complete tagged public views and SSE pull/publication/close driver."""
import json
from copy import deepcopy
from .models import Artifact
from .transport import artifact_from_wire
def public_artifact(raw):
    """Preserve the explicit artifact tag and exact data without content sniffing."""
    artifact=artifact_from_wire(raw)
    return None if artifact is None else {'type':artifact.type,'data':deepcopy(artifact.data)}
def is_terminal(snapshot):return snapshot['state']in('completed','failed')
def final_payload(snapshot):
    return {'task_id':snapshot['id'],'state':snapshot['state'],'artifact':public_artifact(snapshot['artifact'])}
def sse_frame(event,payload):
    return ('event: '+event+'\ndata: '+json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n\n').encode('utf-8')
async def publish_sse(source,projection):
    """Publish each observed snapshot's domain events and close after its terminal state."""
    try:
        async for snapshot in source:
            for event,payload in projection.events(snapshot):yield sse_frame(event,payload)
            if is_terminal(snapshot):break
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
