"""Pinned lesson-local discovery and review result adaptation."""
from .models import ReviewResult
def validate_local_card(card):
    """Validate this lesson's exact local card, including the literal a2a-0.3 pin.

    No newer protocol fields are accepted as substitutes. Extra card keys are
    permitted, but all declared local fields below must have their exact shape.
    """
    if card.get('protocol_version')!='a2a-0.3':raise ValueError('local protocol version')
    if not isinstance(card.get('name'),str)or not card['name']or not isinstance(card.get('version'),str):raise ValueError('local card identity')
    skills=card.get('skills');modes=card.get('modalities');endpoints=card.get('endpoints')
    if not isinstance(skills,list)or not all(isinstance(x,str)for x in skills):raise ValueError('local skills list')
    if not isinstance(modes,list)or not modes or not all(x in ('text','structured')for x in modes):raise ValueError('local modality list')
    if not isinstance(endpoints,dict)or not isinstance(endpoints.get('tasks'),str)or not endpoints['tasks']:raise ValueError('local tasks endpoint')
    if card.get('auth')!={'type':'none'}:raise ValueError('local auth shape')
    return card

def negotiate_review_modality(card,artifact):
    """Require the actual artifact tag to be an advertised local modality."""
    validate_local_card(card)
    if artifact.type not in card['modalities']:raise ValueError('unadvertised artifact modality')
    return artifact.type

def adapt_review(card,envelope):
    """Adapt a successful flat review; explicit text stays opaque.

    The caller supplies the already-correct terminal TaskEnvelope. This local
    schema validates declared lines; it does not run or re-review source code.
    """
    validate_local_card(card)
    if envelope.state!='completed' or envelope.artifact is None:raise ValueError('successful artifact required')
    mode=negotiate_review_modality(card,envelope.artifact)
    if mode=='text':
        if not isinstance(envelope.artifact.data,str):raise ValueError('text review string')
        return ReviewResult(envelope.task_id,mode,text=envelope.artifact.data)
    data=envelope.artifact.data
    if not isinstance(data,dict)or set(data)!={'issues','lines'}:raise ValueError('flat review shape')
    if not isinstance(data['issues'],list)or not all(isinstance(x,str)for x in data['issues']):raise ValueError('review issues list')
    if type(data['lines'])is not int or data['lines']<0:raise ValueError('review lines integer')
    return ReviewResult(envelope.task_id,mode,tuple(data['issues']),data['lines'])
