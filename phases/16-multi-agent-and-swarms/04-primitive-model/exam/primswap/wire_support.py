"""GIVEN JSON Text Sequence encoding, source events and full async publication/close driver."""
import json

def json_sequence_record(value):return b'\x1e'+json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n'

def replay_events(result):
    """Yield existing replay observations and its final typed stop without re-running policies."""
    for decision in result['decisions']:yield {'kind':'decision','value':decision}
    yield {'kind':'stop','value':result['stop']}

async def stream_decisions(source,projection):
    iterator=source.__aiter__()
    try:
        async for event in iterator:
            if event['kind']=='decision':payload=projection.decision(event['value'])
            elif event['kind']=='stop':payload=projection.stop(event['value'])
            else:raise ValueError('local primitive event kind')
            yield json_sequence_record(payload)
    finally:
        close=getattr(iterator,'aclose',None)
        if close is not None:await close()
