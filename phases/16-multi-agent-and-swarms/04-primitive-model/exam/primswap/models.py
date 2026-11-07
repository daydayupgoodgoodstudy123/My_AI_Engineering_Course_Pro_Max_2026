"""GIVEN immutable configuration and typed target outcomes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentDefinition:
    name: str
    system_prompt: str
    tools: tuple[str,...]
    policy_name: str

@dataclass(frozen=True)
class RunConfig:
    mode: str
    order: tuple[str,...] = ()
    start: str | None = None
    max_steps: int = 10

@dataclass(frozen=True)
class Target:
    kind: str
    name: str | None

def step_range(max_steps):
    """GIVEN bounded step primitive; zero is a valid no-execution budget."""
    if type(max_steps) is not int or max_steps<0:raise ValueError('local step budget')
    return range(max_steps)

def validate_definitions(definitions,config):
    """Validate local immutable definition shapes, independent of policy registration."""
    step_range(config.max_steps)
    if config.mode not in ('static','handoff','selector'):raise ValueError('local mode')
    if config.start is not None and not isinstance(config.start,str):raise ValueError('local start')
    if len({item.name for item in definitions})!=len(definitions):raise ValueError('duplicate local agent')
    for item in definitions:
        if not item.name or item.name=='done' or not isinstance(item.system_prompt,str) or not isinstance(item.policy_name,str):raise ValueError('local agent definition')
        if not isinstance(item.tools,tuple) or not all(isinstance(tool,str) for tool in item.tools):raise ValueError('local tools')
