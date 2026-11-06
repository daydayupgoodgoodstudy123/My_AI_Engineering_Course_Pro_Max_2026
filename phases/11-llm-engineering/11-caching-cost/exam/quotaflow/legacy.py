"""Given sequential legacy orchestration; joint retry and atomic admission live elsewhere."""
from dataclasses import replace
from collections import deque
from .contracts import BucketState,Admission,WINDOW_US,integer,validate_policy,validate_state
from .bucket import tier_policy,refill_exact,commit_admission
def expire_rpm(state,now_us):
    stamps=deque(state.rpm)
    while stamps and now_us-stamps[0]>=WINDOW_US:stamps.popleft()
    return replace(state,rpm=tuple(stamps))
class LegacyService:
    def __init__(self,store,policies):self.store=store;self.policies=policies
    def admit(self,user,demand,now_us,tier="free"):
        integer(demand,1);integer(now_us)
        policy=tier_policy(tier,self.policies)
        state=self.store.load(user)
        if state is None:state=BucketState(policy["capacity"],now_us)
        state=refill_exact(state,policy,now_us)
        effective=state.last_refill_us
        state=expire_rpm(state,effective)
        allowed=state.tokens>=demand and len(state.rpm)<policy["max_requests_per_min"]
        state=commit_admission(state,demand,allowed,effective)
        self.store.save(user,state)
        return Admission(allowed,None,"allowed" if allowed else "limited",state.tokens)
