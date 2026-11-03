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
    raise NotImplementedError("TODO 1: route; see PROMPT.md")

def eligible(providers, requirements):
    raise NotImplementedError("TODO 2: eligible; see PROMPT.md")
