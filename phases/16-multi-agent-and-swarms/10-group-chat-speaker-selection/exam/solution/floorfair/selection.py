"""Named-question obligations and actual-turn weighted deficit selection."""
from fractions import Fraction
from .models import Question,Choice
from .support import committed_messages,validate_share_inputs,validate_policy
def update_question_obligations(events):
    """Keep one conversation's typed, uniquely identified questions in creation order.

    Only the named addressee answering the exact ID in that thread resolves one.
    Text mentions without question metadata are ordinary content.
    """
    pending=[]
    for message in committed_messages(events):
        if message.question_id:pending.append(Question(message.question_id,message.thread,message.addressee,message.message_id))
        if message.reply_to:pending=[q for q in pending if not(q.question_id==message.reply_to and q.thread==message.thread and q.addressee==message.speaker)]
    return tuple(pending)
def speaker_deficits(roster,counts):
    """For active speakers use (active_actual_turns+1)*weight/active_weight - actual_count."""
    validate_share_inputs(roster,counts)
    active=tuple(s for s in roster if s.active)
    if not active:return()
    total=sum(counts.get(s.name,0)for s in active);weight=sum(s.weight for s in active)
    return tuple((s.name,Fraction((total+1)*s.weight,weight)-counts.get(s.name,0))for s in active)
def select_next_speaker(roster,counts,pending,last_speaker,consecutive,max_consecutive):
    """Respect the consecutive cap, then oldest eligible named question, then largest deficit/roster tie.

    A cap-blocked question stays pending; another speaker may reset the streak.
    If no active eligible speaker exists, return None instead of inventing speech.
    """
    validate_policy(roster,counts,max_consecutive)
    eligible=tuple(s for s in roster if s.active and not(s.name==last_speaker and consecutive>=max_consecutive))
    if not eligible:return None
    deficits=dict(speaker_deficits(roster,counts));names={s.name for s in eligible}
    for question in pending:
        if question.addressee in names:return Choice(question.addressee,'question:'+question.question_id,deficits[question.addressee])
    selected=max(eligible,key=lambda s:deficits[s.name])
    return Choice(selected.name,'deficit',deficits[selected.name])
