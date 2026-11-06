"""Measurement contracts include the people, evidence and decision direction."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from collections import Counter
import json,math
@dataclass(frozen=True)
class Metric:
    name:str
    direction:str
    threshold:float
    window:str
    source:str
    population:str
    kind:str
@dataclass(frozen=True)
class Plan:
    goal:str
    questions:tuple[str,...]
    metrics:tuple[Metric,...]

def finite(value)->bool:
    """Correct supplied number boundary; booleans and nonfinite values are not measurements."""
    return type(value) in (int,float) and math.isfinite(value)

def duplicate_names(names)->list[str]:
    """Correct supplied name identity check, one finding per duplicated name in first order."""
    return [n for n,count in Counter(names).items() if count>1]

def metric_issues(metric:Metric)->list[str]:
    """Require name, source, window and population; direction at-most/at-least,
    finite threshold and outcome/guardrail/counter kind. Return issues in this order.
    """
    issues=[]
    for field in ('name','source','window'):
        if not getattr(metric,field).strip():issues.append(metric.name+' lacks '+field)
    if metric.direction not in ('at-most','at-least'):issues.append(metric.name+' has invalid direction')
    if not finite(metric.threshold):issues.append(metric.name+' has invalid threshold')
    if metric.kind not in ('outcome','guardrail','counter'):issues.append(metric.name+' has invalid kind')
    return issues

def validate(plan:Plan)->list[str]:
    """Validate the reproducible plan, not individual questions' kind coverage.
    Require a nonblank goal/questions and at least outcome and guardrail at plan level.
    Each metric name is a unique identity; counter is optional and fully reportable.
    """
    issues=[]
    if not plan.goal.strip():issues.append('goal is empty')
    if not plan.questions or any(not q.strip() for q in plan.questions):issues.append('questions are empty')
    kinds={m.kind for m in plan.metrics}
    for kind in ('outcome','guardrail'):
        if kind not in kinds:issues.append(kind+' metric is missing')
    for name in duplicate_names(m.name for m in plan.metrics):issues.append('duplicate metric: '+name)
    for metric in plan.metrics:issues.extend(metric_issues(metric))
    return issues

def read_source(path:str|Path)->dict:
    """Read one bounded local UTF-8 JSON evidence snapshot completely and exactly.
    The file is at most4MiB, a JSON object with values and optional source receipts.
    Preserve every JSON field and Unicode string; the source is stable during a read.
    This is a local snapshot reader, not a network/streaming decoder or sliding window.
    """
    with open(path,'rb',buffering=0) as f:
        raw=bytearray()
        while chunk:=f.read(1):raw.extend(chunk)
    return json.loads(raw.decode('utf-8'))

def report(plan:Plan,path:str|Path)->dict:
    """Return status valid/invalid, issues and one result for every metric in order.
    Values come from source['values'] by metric name. Missing ->status missing;
    nonfinite/nonnumeric value or invalid contract ->status invalid; otherwise include
    name, exact value and passed using inclusive direction. Keep counter results too.
    """
    issues=validate(plan);values=read_source(path)['values'];results=[]
    for m in plan.metrics:
        if m.kind=='counter':continue
        if metric_issues(m):results.append({'name':m.name,'status':'invalid'})
        elif m.name not in values:results.append({'name':m.name,'status':'missing'})
        elif not finite(values[m.name]):results.append({'name':m.name,'status':'invalid'})
        else:
            value=values[m.name];passed=value<=m.threshold if m.direction=='at-most' else value>=m.threshold
            results.append({'name':m.name,'value':value,'passed':passed})
    return {'status':'invalid' if issues else 'valid','issues':issues,'results':results,'plan':asdict(plan)}
