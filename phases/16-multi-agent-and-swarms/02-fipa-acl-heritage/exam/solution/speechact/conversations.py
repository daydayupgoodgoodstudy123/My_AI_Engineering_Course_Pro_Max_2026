"""Local request/subscription obligation automata, one interaction per named key."""
from .models import RequestState,SubscriptionState,interaction_key
def advance_request_obligation(state,message):
    """Advance one local request. request starts pending; reverse-party agree
    makes agreed; reverse-party refuse only pending; inform pending/agreed ends
    done; failure only agreed ends failed. Terminal states reject more acts.
    Every reply must reverse the initial requester/responder pair.
    """
    if state is None:
        if message.performative!="request":raise ValueError("request must open interaction")
        return RequestState(message.sender,message.receiver,"pending")
    if (message.sender,message.receiver)!=(state.responder,state.requester):raise ValueError("request reply parties")
    act=message.performative;current=state.status
    if current=="pending" and act=="agree":status="agreed"
    elif current=="pending" and act=="refuse":status="refused"
    elif current in ("pending","agreed") and act=="inform":status="done"
    elif current=="agreed" and act=="failure":status="failed"
    else:raise ValueError("request act outside local stage")
    return RequestState(state.requester,state.responder,status)
def advance_subscription_obligation(state,message):
    """subscribe opens active; reverse-party inform increments notices and stays
    active; original subscriber->publisher cancel closes only this interaction.
    Closed subscriptions reject further acts. Payload truth does not determine intent.
    """
    if state is None:
        if message.performative!="subscribe":raise ValueError("subscribe must open interaction")
        return SubscriptionState(message.sender,message.receiver,True,0)
    if not state.active:raise ValueError("subscription already cancelled")
    if message.performative=="inform" and (message.sender,message.receiver)==(state.publisher,state.subscriber):
        return SubscriptionState(state.subscriber,state.publisher,True,state.notifications+1)
    if message.performative=="cancel" and (message.sender,message.receiver)==(state.subscriber,state.publisher):
        return SubscriptionState(state.subscriber,state.publisher,False,state.notifications)
    raise ValueError("subscription act or parties")
def recognize_conversations(messages):
    """Consume ordered messages keyed by (protocol, exact conversation_id).

    Return first-seen order dictionaries with protocol, conversation_id, status,
    outstanding and notifications. Requests pending/agreed are outstanding;
    subscriptions remain outstanding until their named cancel. No retries,
    deadlines, multi-request reuse or complete FIPA lifecycle is specified.
    """
    states={}
    for message in messages:
        key=interaction_key(message)
        advance=advance_request_obligation if key[0]=="fipa-request" else advance_subscription_obligation
        states[key]=advance(states.get(key),message)
    rows=[]
    for (protocol,conversation_id),state in states.items():
        if protocol=="fipa-request":status=state.status;outstanding=status in ("pending","agreed");notices=0
        else:status="active" if state.active else "cancelled";outstanding=state.active;notices=state.notifications
        rows.append({"protocol":protocol,"conversation_id":conversation_id,"status":status,"outstanding":outstanding,"notifications":notices})
    return rows
