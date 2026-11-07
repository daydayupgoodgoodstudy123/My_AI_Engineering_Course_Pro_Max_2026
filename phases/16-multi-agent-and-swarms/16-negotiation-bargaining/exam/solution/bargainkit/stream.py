"""Project actual public event fields with the same quote revision's narration; public channels/writer are supplied."""
from .exact import price_field
from .mechanism_support import units
def event_fields(event,catalog):
    """Bind this event's negotiation/phase/numeric quote and matching narration revision without private-state input."""
    q=event.quote;narration=None if q is None else catalog.get(q.uid,event.narration_revision).text
    return {'negotiation_id':event.negotiation_id,'round':event.round,'side':event.side,'kind':event.kind,'price':price_field(None if q is None else q.price),'offer_uid':None if q is None else q.uid,'revision':event.narration_revision,'price_ticks':None if q is None else units(q.price,q.tick),'narration':narration}
