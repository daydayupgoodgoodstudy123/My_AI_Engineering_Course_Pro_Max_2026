"""Private syslog-style drift episodes with a controlled next-step release fake."""
from __future__ import annotations
from collections.abc import AsyncIterable,AsyncIterator,Callable
import json
from .stages import Registration
from .drift import Observation,drift
class EpisodeGate:
    """Correct supplied episode state. Return only newly active reasons in current
    order, per system. Recovery rearms the reason. Empty current clears that system.
    """
    def __init__(self):self.active={}
    def feed(self,key:str,current:list[str])->list[str]:
        old=self.active.get(key,set());new=[r for r in current if r not in old];self.active[key]=set(current);return new

def alert(record:Registration,observation:Observation,reason:str)->str:
    """Correct private text: <134>1 UTC-midnight - stagegate - DRIFT - JSON newline.
    JSON has system,declared,reason. This is not a claim the lesson teaches RFC5424.
    """
    return '<134>1 '+observation.at+'T00:00:00Z - stagegate - DRIFT - '+json.dumps({'system':record.id,'declared':record.declared_stage,'reason':reason},ensure_ascii=False)+'\n'

async def monitor(records:dict[str,Registration],source:AsyncIterable[Observation],release:Callable[[Observation],None])->AsyncIterator[str]:
    """For each full observation snapshot compute every current drift reason.
    Release the controlled fake next step exactly once only if current reasons empty;
    new-alert dedup must never make an already-unsafe snapshot safe. For entered
    episode reasons emit one alert each in drift order, the whole block before pulling
    another observation. A recovered reason may alert again. Do not stop monitoring
    other systems because one is unsafe. Closing at any alert must not prefetch or
    release future steps. Inputs use known ids and immutable declarations.
    """
    gate=EpisodeGate()
    async for observation in source:
        record=records[observation.system];current=drift(record,observation)
        if not current:release(observation)
        for reason in gate.feed(record.id,current):yield alert(record,observation,reason)
