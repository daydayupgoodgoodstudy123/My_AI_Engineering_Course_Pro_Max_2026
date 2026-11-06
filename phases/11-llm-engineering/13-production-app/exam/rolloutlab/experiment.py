"""Percentage rollout versus all-eligible-miss shadow execution and role-aware paid facts."""
from dataclasses import replace
from .contracts import Branch,ExperimentOutcome,ProviderFailure,PaidObservation,PreparedMiss,validate_experiment
from .routing import stable_bucket,get_prompt_record
from .primitives import render_template,request_fact
async def execute_experiment(prepared,experiment,templates,provider,output_guard,evaluator,ledger):
    """Execute branch roles over repaired P1 primitives for a prepared model-call miss.

    Rollout calls exactly one stable-bucket selected served version. Shadow calls
    control served plus variant shadow for every eligible miss, independent of
    traffic_pct. Cache/blocked paths are handled by the correct P1 dispatcher.
    Provider is an injected async replay with correct fallback; it returns text
    and actually observed AttemptFact values, or ProviderFailure(attempts).
    Unobserved failure creates no paid usage. Preserve every observed fact with
    its role/version even if output is safety-replaced. Guard/evaluator/price
    facts are supplied; never recalculate observed usage from public text.
    Isolate branch failures: shadow cannot replace or erase served success, and
    served failure cannot promote shadow. Ledger gets one request observation,
    plus one immutable paid observation per actual fact. No bootstrap/rollback.
    """
    raise NotImplementedError
