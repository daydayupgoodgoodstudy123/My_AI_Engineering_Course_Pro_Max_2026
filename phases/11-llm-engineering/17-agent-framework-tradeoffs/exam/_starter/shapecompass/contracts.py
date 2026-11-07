"""Given value objects, strict input primitives and fixed course rule metadata.

Framework names are lesson fixtures, not current product capability assertions.
No predicate implementation or completed recommendation selector is provided.
"""
from dataclasses import dataclass
import json,re

FLAGS=('has_typed_state','has_roles','has_dialogue','has_parallel_fanout','needs_resume','needs_human_interrupt','needs_session_memory')
@dataclass(frozen=True)
class Problem:
    has_typed_state:bool=False
    has_roles:bool=False
    has_dialogue:bool=False
    has_parallel_fanout:bool=False
    needs_resume:bool=False
    needs_human_interrupt:bool=False
    needs_session_memory:bool=False
    total_llm_calls:int=1
@dataclass(frozen=True)
class Scenario:
    case_id:str
    label:str
    problem:Problem
@dataclass(frozen=True)
class Recommendation:
    framework:str
    reason:str
@dataclass(frozen=True)
class FeatureCard:
    total_llm_calls:int
    signals:tuple
@dataclass(frozen=True)
class ReportRow:
    case_id:str
    label:str
    features:FeatureCard
    recommendation:Recommendation
@dataclass(frozen=True)
class RuleEvaluation:
    rule_id:str
    matched:bool
    evidence:tuple
@dataclass(frozen=True)
class Decision:
    framework:str
    decisive_rule:str
    reason:str
    requirements:tuple
    trace:tuple
@dataclass(frozen=True)
class DecisionCard:
    scenario:Scenario
    decision:Decision
@dataclass(frozen=True)
class RuleNode:
    rule_id:str
    framework:str
    otherwise:object=None

RULE_IDS=('hard','tiny','dialogue','roles','session','typed','fallback')
FRAMEWORKS=('langgraph','plain python','autogen','crewai','agno','langgraph','langgraph')
REASONS={
 'hard':'Explicit resume, interrupt or fanout requirement selects the course graph profile.',
 'tiny':'At most two calls with none of the seven state or shape requirements needs no framework.',
 'dialogue':'Dialogue without typed state selects the course chat profile.',
 'roles':'Roles without typed state selects the course specialist profile.',
 'session':'Session memory without roles or dialogue selects the course agent profile.',
 'typed':'Typed state selects the course graph profile.',
 'fallback':'The course multi-step fallback selects the graph profile.'}
RULE_TREE=None
for _rule,_framework in reversed(tuple(zip(RULE_IDS,FRAMEWORKS))):
    RULE_TREE=RuleNode(_rule,_framework,RULE_TREE)

def call_count(value):
    """Accept a nonnegative integer call count, excluding bool."""
    if type(value) is not int or value<0:raise ValueError('a projected call count is required')
    return value
def normalized_problem(raw):
    if not isinstance(raw,dict) or set(raw)-set(FLAGS)-{'total_llm_calls'}:raise ValueError('problem fields')
    out={key:raw.get(key,False) for key in FLAGS}
    if any(type(value) is not bool for value in out.values()):raise ValueError('strict boolean flag')
    out['total_llm_calls']=call_count(raw.get('total_llm_calls',1))
    return out
def feature_card(problem):
    return FeatureCard(call_count(problem.total_llm_calls),tuple((key,getattr(problem,key)) for key in FLAGS))
def validate_scenarios(rows):
    rows=tuple(rows);ids=[]
    for row in rows:
        if not isinstance(row,Scenario) or not re.fullmatch(r'[A-Za-z0-9_.-]+',row.case_id) or not isinstance(row.label,str):raise ValueError('scenario identity')
        normalized_problem(vars(row.problem));ids.append(row.case_id)
    if len(ids)!=len(set(ids)):raise ValueError('duplicate case_id')
    return rows
def validate_raw_cases(rows):
    rows=tuple(rows);seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'case_id','label','problem'}:raise ValueError('case fields')
        if not isinstance(row['case_id'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',row['case_id']) or row['case_id'] in seen:raise ValueError('case identity')
        if not isinstance(row['label'],str):raise ValueError('case label')
        normalized_problem(row['problem']);seen.add(row['case_id'])
    return rows
def row_text(row,width):
    return f'[{row.case_id}] {row.label:<{width}} -> {row.recommendation.framework:<14} // {row.recommendation.reason} (calls={row.features.total_llm_calls})'
def finish_decision(rule_id,requirements,trace):
    trace=tuple(trace);last=trace[-1]
    reason=REASONS[rule_id]+' Evidence: '+json.dumps(dict(last.evidence),ensure_ascii=False,separators=(',',':'))
    return Decision(FRAMEWORKS[RULE_IDS.index(rule_id)],rule_id,reason,tuple(requirements),trace)
def validate_decision(value):
    if not isinstance(value,Decision) or value.decisive_rule not in RULE_IDS or value.framework not in FRAMEWORKS or not isinstance(value.reason,str):raise ValueError('decision shape')
    if type(value.requirements) is not tuple or any(key not in FLAGS for key in value.requirements):raise ValueError('requirement shape')
    if type(value.trace) is not tuple or not value.trace:raise ValueError('trace shape')
    for row in value.trace:
        if not isinstance(row,RuleEvaluation) or row.rule_id not in RULE_IDS or type(row.matched) is not bool or type(row.evidence) is not tuple:raise ValueError('evaluation shape')
        for key,item in row.evidence:
            if key not in FLAGS+('total_llm_calls',) or type(item) not in (bool,int):raise ValueError('evidence shape')
    return value
def decision_json(value):
    """Given complete lossless codec; it evaluates no recommendation rules."""
    validate_decision(value)
    return {'framework':value.framework,'decisive_rule':value.decisive_rule,'reason':value.reason,'requirements':list(value.requirements),'trace':[{'rule_id':x.rule_id,'matched':x.matched,'evidence':[list(pair) for pair in x.evidence]} for x in value.trace]}
def decision_from_json(value):
    if set(value)!={'framework','decisive_rule','reason','requirements','trace'}:raise ValueError('decision fields')
    result=Decision(value['framework'],value['decisive_rule'],value['reason'],tuple(value['requirements']),tuple(RuleEvaluation(x['rule_id'],x['matched'],tuple(tuple(pair) for pair in x['evidence'])) for x in value['trace']))
    return validate_decision(result)
