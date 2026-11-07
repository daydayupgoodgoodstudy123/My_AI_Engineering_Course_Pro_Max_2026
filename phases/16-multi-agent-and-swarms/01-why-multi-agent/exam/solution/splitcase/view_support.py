"""Given rendering and consumers for declared role-scoped replay facts."""
from .models import InputView,Fact,fact_map

def make_view(role,task,shared_facts,messages,notes):
    facts=list(shared_facts);pieces=[task]
    for message in messages:
        pieces.append(f"[From {message.sender}]: {message.content}");facts.extend(message.facts)
    for note in notes:
        pieces.append(f"[Private {note.owner}]: {note.content}");facts.extend(note.facts)
    values=fact_map(facts)
    return InputView(role.name,"\n".join(pieces),tuple(Fact(k,v) for k,v in values.items()))

def required_fact_value(view,key):
    """Read a fact that the receiving specialist's declared contract requires."""
    return fact_map(view.facts)[key]
