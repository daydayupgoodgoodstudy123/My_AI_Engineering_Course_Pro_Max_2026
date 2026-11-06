"""Atomic token plus admitted-request sliding-window decisions."""
from .contracts import BucketState,Admission,US,WINDOW_US,integer,validate_policy
from .bucket import tier_policy,refill_exact,commit_admission
from .legacy import expire_rpm
class AdmissionController:
    def __init__(self,store,policies):self.store=store;self.policies=policies
    def admit(self,user,demand,now_us,tier="free"):
        """Use one per-user critical section from state load through saved decision.

        Reuse repaired Part 1 refill and conditional bookkeeping. Retry is the
        earliest integer microsecond delay that satisfies tokens AND the admitted
        request 60-second sliding window with no intervening requests. Legal
        ordered history may contain more timestamps than the current RPM limit;
        enough timestamps must expire to leave an available slot. A demand above
        capacity has retry None. Allowed work has retry 0. Denied work may advance
        the refill clock/prune stale history but adds no debit/timestamp/usage.
        Effective time is max(now_us,last_refill_us), including for consumption.
        The supplied lock is in-process only, and policy stays fixed per user.
        """
        raise NotImplementedError
