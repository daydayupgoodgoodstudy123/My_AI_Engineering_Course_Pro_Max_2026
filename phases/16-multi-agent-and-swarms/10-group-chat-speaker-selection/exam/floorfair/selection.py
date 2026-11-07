"""Named-question obligations and actual-turn weighted deficit selection."""
from fractions import Fraction
from .models import Question,Choice
from .support import committed_messages,validate_share_inputs,validate_policy
def update_question_obligations(events):
    """Keep one conversation's typed, uniquely identified questions in creation order.

    Only the named addressee answering the exact ID in that thread resolves one.
    Text mentions without question metadata are ordinary content.
    """
    raise NotImplementedError
def speaker_deficits(roster,counts):
    """For active speakers use (active_actual_turns+1)*weight/active_weight - actual_count."""
    validate_share_inputs(roster,counts)
    raise NotImplementedError
def select_next_speaker(roster,counts,pending,last_speaker,consecutive,max_consecutive):
    """Respect the consecutive cap, oldest eligible named question, then largest deficit/roster tie.

    Cap-blocked questions stay pending. No eligible speaker means None.
    """
    validate_policy(roster,counts,max_consecutive)
    raise NotImplementedError
