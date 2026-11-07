"""Pinned lesson-local discovery and review result adaptation."""
from .models import ReviewResult
def validate_local_card(card):
    """Validate this lesson's exact local card, including the literal a2a-0.3 pin.

    No newer protocol fields are accepted as substitutes. Extra card keys are
    permitted, but all declared local fields below must have their exact shape.
    """
    raise NotImplementedError

def negotiate_review_modality(card,artifact):
    """Require the actual artifact tag to be an advertised local modality."""
    raise NotImplementedError

def adapt_review(card,envelope):
    """Adapt a successful flat review; explicit text stays opaque.

    The caller supplies the already-correct terminal TaskEnvelope. This local
    schema validates declared lines; it does not run or re-review source code.
    """
    raise NotImplementedError
