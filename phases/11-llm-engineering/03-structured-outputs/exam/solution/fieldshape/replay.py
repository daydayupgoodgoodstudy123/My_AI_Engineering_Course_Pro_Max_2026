"""Completed local extraction replay; no retry or token-prefix decoding."""
import json
from .validation import validate_schema

def parse_extraction(raw, schema):
    """Return {status, raw, data, issues} for one completed JSON string.

    status is parse_error (data=None, issues=[]), schema_error (parsed data,
    every validator issue), or ok (parsed data, issues=[]). Keep raw exactly.
    Issues use {path:list[str|int], code:str, message:str}. Do not repair JSON,
    extract fenced blocks, retry, coerce values, or drop invalid completions.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "parse_error", "raw": raw, "data": None, "issues": []}
    issues = validate_schema(data, schema)
    return {"status": "schema_error" if issues else "ok", "raw": raw, "data": data,
            "issues": [{"path": list(issue.path), "code": issue.code, "message": issue.message} for issue in issues]}

async def stream_extractions(source, schema):
    """Given async envelope: one NDJSON event per completed raw string.

    Emit before pulling the next item; close the source if it supports aclose.
    JSON quoting, record delimiters and source cleanup are supplied helpers.
    """
    try:
        async for raw in source:
            yield json.dumps(parse_extraction(raw, schema), ensure_ascii=False) + "\n"
    finally:
        close = getattr(source, "aclose", None)
        if close is not None:
            await close()
