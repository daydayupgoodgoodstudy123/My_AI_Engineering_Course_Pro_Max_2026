"""Tier policy, exact local token refill and caller-decided admission bookkeeping."""
from dataclasses import replace
from .contracts import US,validate_policy,validate_state,integer
def tier_policy(tier,policies):
    """Return the requested policy mapping, with the free policy for an unknown tier."""
    return policies.get(tier,policies["free"])
def refill_exact(state,policy,now_us):
    """Advance an integer-token bucket on an exact microsecond clock.

    Policies have positive integer tokens/second. Remainder is fractional-token
    numerator in millionths. Full capacity discards excess and fractional credit.
    Backward time leaves the effective clock at its previous maximum. Timestamp
    history may exceed max RPM; it is pruned by the supplied expiry helper.
    """
    capacity=policy["capacity"]
    validate_policy(policy);validate_state(state,policy);integer(now_us)
    end=max(now_us,state.last_refill_us)
    elapsed=end-state.last_refill_us
    added,remainder=divmod(elapsed*policy["refill_rate"]+state.remainder,US)
    tokens=min(capacity,state.tokens+added)
    if tokens==capacity:remainder=0
    return replace(state,tokens=tokens,last_refill_us=end,remainder=remainder)
def commit_admission(state,demand,allowed,now_us):
    """Only an allowed decision debits tokens, appends its timestamp and adds usage.

    The caller supplies a feasible decision and effective nondecreasing timestamp;
    this helper does not decide eligibility or calculate a retry time.
    """
    if not allowed:return state
    return replace(state,tokens=state.tokens-demand,rpm=state.rpm+(now_us,),total_used=state.total_used+demand)
