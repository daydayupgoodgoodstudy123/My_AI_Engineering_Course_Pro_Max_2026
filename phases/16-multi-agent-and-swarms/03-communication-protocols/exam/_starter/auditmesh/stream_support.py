"""GIVEN SSE serialization and complete async pull/publication/close driver."""
import json

def sse(event,data):return 'event: '+event+'\ndata: '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n\n'

async def stream_audit(source,projection):
    """Publish each candidate domain result before another source pull; always close source."""
    iterator=source.__aiter__()
    try:
        async for event in iterator:
            if event['kind']=='step':result=projection.on_step(event['run_id'],event['step'])
            elif event['kind']=='sealed':result=projection.on_seal(event['receipt'])
            else:raise ValueError('local audit stream kind')
            yield sse(*result)
        projection.finish()
    finally:
        close=getattr(iterator,'aclose',None)
        if close is not None:await close()
