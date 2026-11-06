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
        integer(demand,1);integer(now_us)
        policy=tier_policy(tier,self.policies);validate_policy(policy)
        with self.store.atomic(user):
            state=self.store.load(user)
            if state is None:state=BucketState(policy["capacity"],now_us)
            state=refill_exact(state,policy,now_us)
            effective=state.last_refill_us
            state=expire_rpm(state,effective)
            if demand>policy["capacity"]:
                self.store.save(user,state)
                return Admission(False,None,"capacity",state.tokens)
            numerator=max(0,(demand-state.tokens)*US-state.remainder)
            token_wait=(numerator+policy["refill_rate"]-1)//policy["refill_rate"]
            rpm_wait=0
            if len(state.rpm)>=policy["max_requests_per_min"]:
                position=len(state.rpm)-policy["max_requests_per_min"]
                rpm_wait=state.rpm[position]+WINDOW_US-effective
            retry=max(token_wait,rpm_wait)
            allowed=retry==0
            reason="allowed" if allowed else "both" if token_wait and rpm_wait else "tokens" if token_wait else "rpm"
            state=commit_admission(state,demand,allowed,effective)
            self.store.save(user,state)
            return Admission(allowed,retry,reason,state.tokens)
