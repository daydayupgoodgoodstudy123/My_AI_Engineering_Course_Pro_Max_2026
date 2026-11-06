"""Given domain records, validated teaching tables and pure comparison primitives."""
from dataclasses import dataclass
import ast,math,operator
OPS={"=":operator.eq,">":operator.gt,"<":operator.lt,">=":operator.ge,"<=":operator.le}
def accepts(kind,value):
    if kind=="number":return type(value) is int or (type(value) is float and math.isfinite(value))
    return type(value) is {"string":str,"boolean":bool}.get(kind)
def require_literal(kind,value,op):
    if op not in OPS or not accepts(kind,value) or (kind=="boolean" and op!="="):raise ValueError("invalid typed comparison")
@dataclass(frozen=True)
class Table:
    name: str
    schema: tuple
    rows: tuple
    def __post_init__(self):
        if not self.name or len({name for name,kind in self.schema})!=len(self.schema):raise ValueError("invalid table schema")
        if any(kind not in ("string","number","boolean") for name,kind in self.schema):raise ValueError("unknown column type")
        if any(len(row)!=len(self.schema) or any(not accepts(kind,value) for (_,kind),value in zip(self.schema,row)) for row in self.rows):raise ValueError("invalid typed table row")
@dataclass(frozen=True)
class Bound:
    index: int
    op: str
    value: object
    def __call__(self,row):return OPS[self.op](row[self.index],self.value)
@dataclass(frozen=True)
class Plan:
    table: Table
    predicates: tuple
    projection: tuple
def validate_plan(plan):
    """Given complete bound-metadata validation before any row is evaluated."""
    width=len(plan.table.schema)
    for pred in plan.predicates:
        if type(pred.index) is not int or not 0<=pred.index<width:raise ValueError("bound field index")
        require_literal(plan.table.schema[pred.index][1],pred.value,pred.op)
    if any(type(i) is not int or not 0<=i<width for i in plan.projection):raise ValueError("bound projection")
def query_shape(spec):
    """Given object/list shape checks, without table/field/operator binding."""
    if type(spec) is not dict or not {"table","filters"}<=set(spec)<= {"table","filters","projection"}:raise ValueError("query object shape")
    if type(spec["table"]) is not str or type(spec["filters"]) is not list:raise ValueError("query fields")
    for item in spec["filters"]:
        if type(item) is not dict or set(item)!={"field","op","value"} or type(item["field"]) is not str or type(item["op"]) is not str:raise ValueError("condition shape")
    if "projection" in spec and (type(spec["projection"]) is not list or any(type(x) is not str for x in spec["projection"])):raise ValueError("projection shape")
@dataclass(frozen=True)
class Invocation:
    ordinal: int
    tool: str
    arguments: dict
    result: object
    elapsed_us: int
@dataclass(frozen=True)
class Probe:
    number: int
    label: str
    run: object
@dataclass(frozen=True)
class Issue:
    kind: str
    path: tuple
    line: int
    column: int
UNSAFE={"exec","eval","compile","__import__","open","globals","locals","vars","getattr","setattr","delattr"}
def parse_code(code):return ast.parse(code)
