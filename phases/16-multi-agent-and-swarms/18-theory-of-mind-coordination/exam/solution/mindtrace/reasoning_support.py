"""Complete subject/action binding and chronological history; no belief interpretation or target solver."""
def subject_actions(snapshot,observer,subject,now):
    selected=[o for o in snapshot.observations if o.key.observer==observer and o.key.subject==subject and o.kind=='action'and o.turn<=now]
    return tuple(sorted(selected,key=lambda o:(o.turn,o.ordinal)))
def validate_prior(prior):
    if len(set(prior.believed_available))!=len(prior.believed_available)or len(set(prior.preference))!=len(prior.preference):raise ValueError('unique perceived candidates and preference required')
