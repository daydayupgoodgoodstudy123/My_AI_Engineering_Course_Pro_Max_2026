"""Complete deterministic local GET replay and exact response snapshots."""
import json
from urllib.parse import urlsplit
class LocalTransport:
    """Timelines map peer URL then task ID to sorted (tick, wire-document) pairs."""
    def __init__(self,timelines):
        self._timelines={peer:{tid:tuple((tick,json.dumps(doc,ensure_ascii=False,allow_nan=False))for tick,doc in frames)for tid,frames in tasks.items()}for peer,tasks in timelines.items()}
        self.get_count=0
    def read_task(self,peer,task_id,tick):
        frames=self._timelines[peer][task_id]
        index=len(frames)-1
        while index and frames[index][0]>tick:index-=1
        return json.loads(frames[index][1])
    def get(self,url,tick,route_parser):
        self.get_count+=1
        split=urlsplit(url);prefix=split.path.rsplit('/',1)[0]
        peer=f'{split.scheme}://{split.netloc}{prefix}'
        route=split.path+('?' + split.query if split.query else '')
        return self.read_task(peer,route_parser(route),tick)
def artifact_from_wire(raw):
    from .models import Artifact
    return None if raw is None else Artifact(raw['type'],raw['data'])
def envelope_status(envelope):
    """Render an already-classified terminal receipt without examining artifact content."""
    if envelope.state=='completed':return 'result'
    if envelope.state=='failed':return 'error'
    if envelope.state=='timeout':return 'timeout'
    raise ValueError('terminal envelope required')
