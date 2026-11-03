"""Original Phase 13 / Lesson 21 CoderPad practice.

Lesson source: 21-llm-routing-layer/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
class TransientError(Exception):
    pass

class ExhaustedError(Exception):

    def __init__(self, attempted):
        super().__init__('providers exhausted')
        self.attempted = attempted

def route(providers, prompt, prices):
    attempted = []
    for name, call in providers:
        attempted.append(name)
        try:
            r = call(prompt)
        except TransientError:
            continue
        return {'provider': name, 'text': r['text'], 'attempted': attempted, 'cost': r['input_tokens'] * prices[name][0] + r['output_tokens'] * prices[name][1]}
    raise ExhaustedError(attempted)

def eligible(providers, requirements):
    return [p['name'] for p in sorted(providers, key=lambda p: (p['price'], p['name'])) if requirements <= p['capabilities']]
