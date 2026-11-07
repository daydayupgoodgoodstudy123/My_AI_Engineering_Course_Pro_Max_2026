"""Immutable logical task observations; time units are integer microseconds."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Task:
    task_id:str
    topic:str
    payload:str
    arrival_us:int
    duration_us:int
    priority:int=0
    pre_assigned:str=''
@dataclass(frozen=True)
class Worker:
    uid:str
    topics:tuple[str,...]
    pool:str='main'
@dataclass(frozen=True, slots=True, order=False)
class Completion:
    task_id:str
    worker_uid:str
    start_us:int
    finish_us:int
    value:str
@dataclass(frozen=True, slots=True, order=False)
class Lifecycle:
    kind:str
    task_id:str
    time_us:int
    worker_uid:str=''
    start_us:int|None=None
    finish_us:int|None=None
    value:str|None=None
    priority:int|None=None
@dataclass(frozen=True, slots=True, order=False)
class Event:
    time_us:int
    sequence:int
    kind:str
    task_id:str
    worker_uid:str=''
    start_us:int|None=None
    value:str|None=None
@dataclass(frozen=True, slots=True, order=False)
class RunReport:
    tasks:tuple[Task,...]
    workers:tuple[Worker,...]
    trace:tuple[Lifecycle,...]
    completions:tuple[Completion,...]
    counts:tuple[tuple[str,int],...]
    cards:tuple[tuple,...]
    unfinished:tuple[str,...]
    finished_us:int
@dataclass(frozen=True)
class TraceArchive:
    tasks:tuple[Task,...]
    workers:tuple[Worker,...]
    trace:tuple[Lifecycle,...]
@dataclass(frozen=True)
class Pool:
    pool_id:str
    shared:bool=False
@dataclass(frozen=True)
class Group:
    name:str
    topics:tuple[str,...]|None
    pools:tuple[Pool,...]=()
    workers:tuple[Worker,...]=()
    children:tuple['Group',...]=()
