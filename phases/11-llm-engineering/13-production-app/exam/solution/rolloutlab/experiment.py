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
    if not isinstance(prepared,PreparedMiss):raise ValueError("prepared miss required")
    validate_experiment(experiment)
    request=prepared.request
    if request.template!=experiment.template:raise ValueError("experiment template")
    bucket=stable_bucket(request.user,experiment.experiment_id)
    plan=[("served",experiment.variant if bucket<experiment.traffic_pct else experiment.control)] if experiment.mode=="rollout" else [("served",experiment.control),("shadow",experiment.variant)]
    branches=[]
    for role,version in plan:
        record=get_prompt_record(templates,experiment.template,version)
        rendered=render_template(record,request.variables)
        try:
            reply=await provider(record,rendered)
        except ProviderFailure as exc:
            facts=exc.attempts;status="error";text="Service unavailable.";quality=None;error=str(exc)
        else:
            facts=reply.attempts;safety=output_guard(reply.text)
            status="approved" if safety.passed else "blocked_output";text=safety.text
            quality=evaluator(record,text,status);error=None
        observations=tuple(PaidObservation(request.request_id,request.user,experiment.experiment_id,role,version,i,fact.model,fact.input_tokens,fact.output_tokens,fact.cost_text) for i,fact in enumerate(facts))
        for observation in observations:ledger.append(observation)
        branches.append(Branch(role,version,status,text,quality,error,observations))
    served=next(b for b in branches if b.role=="served")
    shadow=tuple(b for b in branches if b.role=="shadow")
    ledger.append(request_fact(replace(request,version=served.version),served.status))
    return ExperimentOutcome(request.request_id,bucket,served,shadow)
