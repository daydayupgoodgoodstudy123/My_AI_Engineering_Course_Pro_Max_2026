"""Discovery wiring, query-free task routing and terminal receipt producers."""
from urllib.parse import quote,urlsplit,unquote
from .models import TaskEnvelope
from .transport import artifact_from_wire
def make_poll_url(endpoint,task_id,query=''):
    """Poll the discovered tasks endpoint with the opaque task ID and optional query."""
    return 'http://default-peer.local/tasks/'+quote(task_id,safe='')+('?' + query if query else '')
def task_id_from_route(route):
    """Extract the decoded task ID from a local /tasks/<id> request target."""
    return unquote(route.split('/tasks/',1)[1])
def classify_terminal(document,tick):
    """Return a terminal typed receipt, preserving failed task state and artifact."""
    state=document['state']
    if state not in ('completed','failed'):return None
    return TaskEnvelope(document['id'],'completed',artifact_from_wire(document['artifact']),tick)
