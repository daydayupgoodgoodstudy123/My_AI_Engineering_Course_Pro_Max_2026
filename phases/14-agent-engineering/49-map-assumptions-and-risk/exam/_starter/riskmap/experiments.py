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
    raise NotImplementedError
