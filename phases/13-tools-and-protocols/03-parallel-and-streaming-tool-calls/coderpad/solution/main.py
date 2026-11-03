"""Original Phase 13 / Lesson 03 CoderPad practice.

Lesson source: 03-parallel-and-streaming-tool-calls/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
import json
from concurrent.futures import ThreadPoolExecutor

def assemble(events):
    buffers = {}
    for event in events:
        index = event.get('index')
        if type(index) is not int or index < 0:
            raise ValueError('index')
        buf = buffers.setdefault(index, {'arguments': ''})
        for key in ('id', 'name'):
            if key in event:
                value = event[key]
                if not isinstance(value, str) or not value or (key in buf and buf[key] != value):
                    raise ValueError(key)
                buf[key] = value
        fragment = event.get('arguments', '')
        if not isinstance(fragment, str):
            raise ValueError('fragment')
        buf['arguments'] += fragment
    result, ids = ([], set())
    for index in sorted(buffers):
        b = buffers[index]
        if 'id' not in b or 'name' not in b or b['id'] in ids:
            raise ValueError('identity')
        args = json.loads(b['arguments'])
        if not isinstance(args, dict):
            raise ValueError('arguments')
        ids.add(b['id'])
        result.append({'id': b['id'], 'name': b['name'], 'arguments': args})
    return result

def parallel(calls, executor, workers=3):
    if type(workers) is not int or workers <= 0:
        raise ValueError('workers')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(executor, calls))
