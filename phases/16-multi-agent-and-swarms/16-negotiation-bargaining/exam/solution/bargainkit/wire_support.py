"""Complete public event classification, exact narrative lookup, terminal gating and NDJSON async lifecycle."""
import json
from .models import PublicEvent
from .exact import price_field
class NarrationCatalog:
    def __init__(self,offers):self._items={(p.quote.uid,p.quote.revision):p.narration for p in offers}
    def get(self,uid,revision):return self._items[uid,revision]
def public_events(result):
    events=[PublicEvent(p.quote.negotiation_id,p.quote.round,p.quote.side,'offer',p.quote,p.quote.revision)for p in result.new_offers]
    s=result.saved.state
    if result.status=='deal':
        settlement=s.settlement;allquotes=[p.quote for p in result.saved.offers]+[q for q in(s.buyer_quote,s.seller_quote)if q is not None]
        quote=next(q for q in allquotes if q.uid==settlement.standing_uid)
        events.append(PublicEvent(s.negotiation_id,s.round,quote.side,'accept',quote,quote.revision))
    else:events.append(PublicEvent(s.negotiation_id,s.round,s.next_side,'no-deal',None,None))
    return tuple(events)
async def publish_events(source,catalog,project):
    terminal=set()
    try:
        async for event in source:
            if event.negotiation_id in terminal:continue
            if event.kind in('accept','no-deal'):terminal.add(event.negotiation_id)
            yield json.dumps(project(event,catalog),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
