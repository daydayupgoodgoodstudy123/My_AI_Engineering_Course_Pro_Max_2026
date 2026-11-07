"""Specialist input projection from explicit addressed summaries and private notes."""
from .view_support import make_view

def specialist_input(role,task,shared_facts,messages,private_notes):
    """Return task facts, addressed messages and only this role's private notes.

    Preserve caller message order and text. Other recipients and other owners
    are outside this specialist's context; task facts remain shared.
    """
    addressed=[message for message in messages if message.recipient==role.name]
    notes=[note for note in private_notes if note.owner==role.name]
    return make_view(role,task,shared_facts,addressed,notes)
