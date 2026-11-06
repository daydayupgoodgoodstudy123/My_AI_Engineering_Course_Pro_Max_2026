"""Given strict observation, run-id, statistical-parameter and suite shape contracts."""
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
import re
@dataclass(frozen=True)
class Observation:
    case_id: str
    category: str
    criterion: str
    input_text: str
    model_output: str
    reference_output: object
    score_text: object
    reasoning: str
@dataclass(frozen=True)
class RunMeta:
    model: str
    prompt_version: str
    seed: int
    notes: str
@dataclass(frozen=True)
class Interval:
    count: int
    mean: float
    lower: float
    upper: float
@dataclass(frozen=True)
class Comparison:
    overall: object
    criteria: dict
    categories: dict
    accepted: bool
@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    criteria: tuple
@dataclass(frozen=True)
class CategorySpec:
    name: str
    cases: tuple
@dataclass(frozen=True)
class SuiteSpec:
    name: str
    categories: tuple
def score_number(text):
    """Given finite 0..5 decimal score conversion; the original spelling stays in storage."""
    if type(text) is not str or not text:raise ValueError("score spelling")
    try:value=Decimal(text)
    except InvalidOperation:raise ValueError("score spelling")
    if not value.is_finite() or not Decimal(0)<=value<=Decimal(5):raise ValueError("score range")
    return float(value)
def indexed_observations(rows):
    """Given unique case/criterion index and primitive row checks, without run pairing."""
    indexed={};categories={}
    for row in rows:
        for value in (row.case_id,row.category,row.criterion):
            if type(value) is not str or not value:raise ValueError("observation identity")
        if any(type(x) is not str for x in (row.input_text,row.model_output,row.reasoning)):raise ValueError("observation text")
        if row.reference_output is not None and type(row.reference_output) is not str:raise ValueError("reference text")
        if row.score_text is not None:score_number(row.score_text)
        key=(row.case_id,row.criterion)
        if key in indexed or (row.case_id in categories and categories[row.case_id]!=row.category):raise ValueError("duplicate/inconsistent observation")
        indexed[key]=row;categories[row.case_id]=row.category
    return indexed
def run_folder(root,run_id):
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+",run_id):raise ValueError("run id")
    return root/run_id
def statistics_parameters(samples,confidence,seed,tolerance):
    if type(samples) is not int or samples<1 or type(seed) is not int:raise ValueError("sampling parameters")
    if type(confidence) not in (int,float) or not 0<confidence<1:raise ValueError("confidence")
    if type(tolerance) not in (int,float) or not 0<=tolerance<=5:raise ValueError("tolerance")
def validate_suite(suite,baseline,variant,comparison):
    """Given catalog/identity checks; ordered hierarchy and pair coverage remain work."""
    known={};category_names=set()
    for category in suite.categories:
        if not category.name or category.name in category_names:raise ValueError("category identity")
        category_names.add(category.name)
        for case in category.cases:
            if not case.case_id or case.case_id in known or len(set(case.criteria))!=len(case.criteria) or any(type(c) is not str or not c for c in case.criteria):raise ValueError("case identity")
            known[case.case_id]=(category.name,set(case.criteria))
    b=indexed_observations(baseline);v=indexed_observations(variant)
    for (case_id,criterion),row in list(b.items())+list(v.items()):
        if case_id not in known or criterion not in known[case_id][1] or row.category!=known[case_id][0]:raise ValueError("observation outside suite")
    if not set(comparison.categories)<=category_names:raise ValueError("evidence outside suite")
    return b,v
