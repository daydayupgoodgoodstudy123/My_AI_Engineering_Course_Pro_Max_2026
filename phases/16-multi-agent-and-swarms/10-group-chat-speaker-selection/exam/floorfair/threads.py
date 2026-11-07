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
    raise NotImplementedError
def inspect_threads(root):
    """Audit own agent quotas, own pending state and inherited subtree speech budgets.

    Inputs are a finite typed thread tree with unique global question IDs and
    resolvable references. Complete catalog reply evidence supplies authorized
    answer IDs/issues; do not implement reply authority here. Own completion
    does not require child completion. Each total limit covers its subtree;
    remaining is the tightest nonnegative own/ancestor residual. max_speaks
    instead covers only each node's own cumulative messages per declared agent.
    """
    raise NotImplementedError
