"""Complete UTF8 byte framing and async pull/publication/close driver."""
import json,struct

def frame(payload):
    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return struct.pack('>I',len(raw))+raw
async def encode_events(source,projection):
    try:
        async for event in source:yield frame(projection.event_payload(event))
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
