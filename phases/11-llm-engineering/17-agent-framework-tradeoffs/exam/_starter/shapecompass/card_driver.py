"""Given current-scenario pull-through and source cancellation/close."""
from .contracts import DecisionCard,validate_scenarios,validate_decision
async def stream_cards(source):
    from .cards import render_card
    try:
        async for event in source:
            if not isinstance(event,DecisionCard):raise ValueError('card event')
            validate_scenarios((event.scenario,));validate_decision(event.decision)
            yield render_card(event)
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
