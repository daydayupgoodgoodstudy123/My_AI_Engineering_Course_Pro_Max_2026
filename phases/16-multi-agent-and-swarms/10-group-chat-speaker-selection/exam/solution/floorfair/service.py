"""Complete local selector/agent observation loop; no question-aware policy is supplied here."""
from .models import Decision,Utterance,ChatReport
from .support import validate
from .context import recent_selector_context
from .primitives import is_terminal_message,record_committed_turn
class ChatDesk:
    def run(self,thread,roster,selector,*,history=(),window=3,max_rounds=20,baseline=()):
        """Invoke each actual selector with its recent input, audit choices, and commit accepted speech.

        The round cap bounds selection attempts. Rejected choices are auditable but
        do not produce utterances. A None selector result means no further proposal.
        Existing user-context history is retained; baseline is supplied prior agent counts.
        """
        roster=tuple(roster);counts=dict(baseline)if baseline else{s.name:0 for s in roster};validate(roster,window,max_rounds,counts)
        pool=list(history);records=[];names={s.name for s in roster};stop='max_rounds'
        for attempt in range(max_rounds):
            context=recent_selector_context(pool,window);proposal=selector(context,dict(counts))
            if proposal is None:stop='selector_exhausted';break
            if proposal.speaker is not None and proposal.speaker not in names:raise ValueError('selector outside roster')
            decision_id=thread+':d'+str(attempt)
            accepted=proposal.accepted and proposal.speaker is not None
            decision=Decision(thread,decision_id,proposal.speaker,proposal.reason,context,sum(counts.values()),accepted,proposal.private_prompt)
            records.append(decision);record_committed_turn(counts,decision)
            if proposal.speaker is None:stop='no_speaker';break
            if not accepted:continue
            message=Utterance(thread,thread+':m'+str(attempt),proposal.speaker,proposal.content,sum(counts.values())+1,decision_id,proposal.question_id,proposal.addressee,proposal.reply_to,proposal.verdict)
            pool.append(message);records.append(message);record_committed_turn(counts,message)
            if is_terminal_message(message.content):stop='terminal';break
        return ChatReport(thread,roster,tuple(pool),tuple(records),tuple(counts.items()),stop)
