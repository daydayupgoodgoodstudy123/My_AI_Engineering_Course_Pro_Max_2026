"""A controlled pilot with a predeclared consecutive-error stop rule."""
from __future__ import annotations
import json
from collections.abc import AsyncIterable,AsyncIterator
from .model import StopRule

def sse(event: str,payload: dict) -> str:
    """Supplied SSE serializer: one JSON data line and one blank terminator."""
    return 'event: '+event+'\ndata: '+json.dumps(payload,ensure_ascii=False)+'\n\n'

async def pilot_stream(source: AsyncIterable[bool], rule: StopRule, error_limit: int) -> AsyncIterator[str]:
    """error_limit is a positive actual int. Each bool is one correct/incorrect
    observed outcome. Immediately emit measurement(count,correct,errors), with
    consecutive errors reset by a correct result. At the limit, emit a decision
    {action: rule.failed, reason: consecutive-errors} after that measurement, then
    stop without pulling more. At EOF emit rule.passed/reason complete if any samples,
    otherwise rule.ambiguous/reason no-evidence. Closing at any yield reads no future
    observation. Inputs are valid, rule fields nonblank. Use supplied SSE encoding.
    """
    count=errors=0
    async for correct in source:
        count+=1
        errors=0 if correct else errors+1
        yield sse('measurement',{'count':count,'correct':correct,'errors':errors})
        if errors>=error_limit:
            yield sse('decision',{'action':rule.failed,'reason':'consecutive-errors'})
            return
    yield sse('decision',{'action':rule.passed if count else rule.ambiguous,'reason':'complete' if count else 'no-evidence'})
