"""Local request/subscription obligation automata, one interaction per named key."""
from .models import RequestState,SubscriptionState,interaction_key
def advance_request_obligation(state,message):
    """Advance one local request. request starts pending; reverse-party agree
    makes agreed; reverse-party refuse only pending; inform pending/agreed ends
    done; failure only agreed ends failed. Terminal states reject more acts.
    Every reply must reverse the initial requester/responder pair.
    """
    raise NotImplementedError("advance_request_obligation")
def advance_subscription_obligation(state,message):
    """subscribe opens active; reverse-party inform increments notices and stays
    active; original subscriber->publisher cancel closes only this interaction.
    Closed subscriptions reject further acts. Payload truth does not determine intent.
    """
    raise NotImplementedError("advance_subscription_obligation")
def recognize_conversations(messages):
    """Consume ordered messages keyed by (protocol, exact conversation_id).

    Return first-seen order dictionaries with protocol, conversation_id, status,
    outstanding and notifications. Requests pending/agreed are outstanding;
    subscriptions remain outstanding until their named cancel. No retries,
    deadlines, multi-request reuse or complete FIPA lifecycle is specified.
    """
    raise NotImplementedError("recognize_conversations")
