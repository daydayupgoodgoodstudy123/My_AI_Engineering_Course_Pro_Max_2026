"""Apply evidence to a previously registered decision threshold."""
from __future__ import annotations
from .model import Assumption, Experiment, Sample, Outcome, instant, validate_experiment

def judge(item: Assumption, exp: Experiment, samples: list[Sample]) -> Outcome:
    """Use the first sample_size observations in arrival order, never later values.
    Registration must precede the earliest used observation in real time (equality
    is invalid), including a partial batch. Missing samples are ambiguous: leave
    uncertainty unchanged and return status open. Otherwise compare the mean using
    the inclusive at-least/at-most threshold. A decisive result reduces uncertainty
    by one, clamped at one, whether supporting or rejecting. Return the corresponding
    explicit pass/fail/ambiguous action verbatim. Assumption identity must match.
    """
    validate_experiment(exp)
    if item.id != exp.assumption_id: raise ValueError('experiment assumption mismatch')
    used=samples[:exp.sample_size]
    if used and instant(exp.registered_at) >= min(instant(s.at) for s in used):
        raise ValueError('threshold was not pre-registered')
    if len(used)<exp.sample_size:
        return Outcome('open',exp.ambiguous_action,item.uncertainty)
    mean=sum(s.value for s in used)/len(used)
    passed=mean>=exp.threshold if exp.direction=='at-least' else mean<=exp.threshold
    return Outcome('supported' if passed else 'rejected', exp.pass_action if passed else exp.fail_action,
                   max(1,item.uncertainty-1))
