"""Original Phase 13 / Lesson 23 CoderPad practice.

Lesson source: 23-capstone-tool-ecosystem/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def run(client, tool, args, allowed, max_polls=3):
    if type(max_polls) is not int or max_polls < 0:
        raise ValueError('budget')
    if tool not in allowed:
        raise PermissionError(tool)
    trace = ['discover']
    if tool not in client.discover():
        raise KeyError(tool)
    result = client.call(tool, args)
    trace.append('call')
    for _ in range(max_polls):
        if result['status'] != 'working':
            break
        result = client.poll(result['task_id'])
        trace.append('poll')
    status = result['status'] if result['status'] != 'working' else 'timeout'
    return {'status': status, 'value': result.get('value') if status == 'completed' else None, 'trace': trace}

def evidence(report):
    return {'completed': report['status'] == 'completed', 'polls': report['trace'].count('poll'), 'live_integration': False}
