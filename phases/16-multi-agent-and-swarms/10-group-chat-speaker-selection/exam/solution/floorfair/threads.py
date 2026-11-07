"""Own-thread cumulative agent quotas and nested total speech budgets."""
from .models import SpeakerQuota
from .thread_support import ThreadCatalog,validate_speaker_limits
def audit_speaker_quotas(actual_messages,max_speaks):
    """Audit each declared speaker's cumulative own-thread utterances, in cap declaration order.

    actual_messages is the typed Utterance sequence supplied by committed_at.
    A speaker's cap-th message is allowed, and its cap+1st message is the first
    excess witness. All messages, including excess, contribute to used. Return
    first_excess as zero or one actual message ID, retaining even an empty ID.
    No declaration produces no quota row. Another speaker does not reset usage;
    these cumulative caps are independent of the P3 consecutive-streak policy.
    Complete supplied validation accepts unique speaker names/nonnegative int caps.
    """
    validate_speaker_limits(max_speaks)
    rows=[]
    for speaker,limit in max_speaks:
        messages=tuple(message for message in actual_messages if message.speaker==speaker)
        used=len(messages)
        first_excess=tuple(message.message_id for message in messages[limit:limit+1])
        rows.append(SpeakerQuota(speaker,limit,used,max(0,limit-used),first_excess))
    return tuple(rows)
def inspect_threads(root):
    """Audit own agent quotas, own pending state and inherited subtree speech budgets.

    Inputs are a finite typed thread tree with unique global question IDs and
    resolvable references. Complete catalog reply evidence supplies authorized
    answer IDs/issues; do not implement reply authority here. Own completion
    does not require child completion. Each total limit covers its subtree;
    remaining is the tightest nonnegative own/ancestor residual. max_speaks
    instead covers only each node's own cumulative messages per declared agent.
    """
    catalog=ThreadCatalog(root)
    used={path:sum(len(catalog.committed_at(p))for p in catalog.subtree_paths(path))for path in catalog.nodes}
    def visit(node,path):
        messages=catalog.committed_at(path);answered,issues=catalog.reply_evidence(path)
        pending=tuple((m.question_id,m.addressee)for m in messages if m.question_id and m.question_id not in answered)
        budget=max(0,min(catalog.nodes[a].limit-used[a]for a in catalog.ancestors(path)))
        children=tuple(visit(child,path+(child.name,))for child in node.children)
        return{'path':path,'pending':pending,'remaining':budget,'issues':tuple(issues),'complete':not pending,'children':children,'speaker_quota':audit_speaker_quotas(messages,node.max_speaks)}
    return visit(root,(root.name,))
