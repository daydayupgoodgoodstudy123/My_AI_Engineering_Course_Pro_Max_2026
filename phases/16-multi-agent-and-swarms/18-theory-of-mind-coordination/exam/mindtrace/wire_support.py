"""Complete observer/time admission, logical key path, explicit operation classifier and JSON Patch lifecycle."""
import json
from .models import BeliefKey,ModelDelta,PatchBatch
from .codec import encode
def pointer_component(value):return str(value).replace('~','~0').replace('/','~1')
def logical_path(key):return '/models/'+pointer_component(json.dumps(key.observer,ensure_ascii=False))+'/'+pointer_component(json.dumps(key.subject,ensure_ascii=False))+'/'+pointer_component(key.proposition)
def admitted_deltas(batch):return tuple(d for d in batch.deltas if d.key.observer==batch.observer and d.turn<=batch.now)
def operation_kind(delta):
    if delta.op not in('replace','remove'):raise ValueError('declared set/remove operation required')
    return delta.op
def patch_value(delta):return encode(delta.value)
def publish_patches(batches,project):
    try:return tuple(json.dumps(project(b),ensure_ascii=False)for b in batches)
    finally:
        close=getattr(batches,'close',None)
        if close is not None:close()
def parse_patches(text):
    value=json.loads(text)
    if not isinstance(value,list):raise ValueError('patch document required')
    for row in value:
        if row.get('op')not in('replace','remove')or not isinstance(row.get('path'),str)or not row['path'].startswith('/models/'):raise ValueError('typed patch required')
        if set(row)!=({'op','path','value'}if row['op']=='replace'else{'op','path'}):raise ValueError('exact operation fields required')
    return value
def model_deltas(observer,predictions,turn):
    """Bind already computed candidate predictions; do not interpret or predict subject models here."""
    return tuple(ModelDelta(BeliefKey(observer,p.subject,'predicted-target'),'replace',p.target,turn,'prediction:'+str(i))for i,p in enumerate(predictions))
