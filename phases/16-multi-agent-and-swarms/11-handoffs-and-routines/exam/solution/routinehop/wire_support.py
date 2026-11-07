"""Complete receipt classification, NDJSON writing and async pull/publish/close driver."""
import json
from .models import CallResult,Transfer,CallSkipped,CallFailed,Reply
def receipt_kind(receipt):
    return{CallResult:'call-result',Transfer:'transfer',CallSkipped:'call-skipped',CallFailed:'call-failed',Reply:'reply'}[type(receipt)]
def encode_line(payload):return(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')
async def publish_receipts(source,projection):
    try:
        async for receipt in source:yield encode_line(projection.payload(receipt))
    finally:await source.aclose()
