"""Original interview practice for 16-multi-agent-and-swarms/01-why-multi-agent.

Local source: phases/16-multi-agent-and-swarms/01-why-multi-agent/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def amdahl(serial_fraction, speedup):
    if not 0 <= serial_fraction <= 1 or speedup < 1:
        raise ValueError('parameters')
    return 1 / (serial_fraction + (1 - serial_fraction) / speedup)

def token_cost(usage, prices):
    totals = {}
    for r in usage:
        pin, pout = prices[r['provider']]
        if pin < 0 or pout < 0 or any((type(r[k]) is not int or r[k] < 0 for k in ('input_tokens', 'output_tokens'))):
            raise ValueError('usage')
        totals[r['provider']] = totals.get(r['provider'], 0) + r['input_tokens'] * pin + r['output_tokens'] * pout
    return {'total': sum(totals.values()), 'by_provider': totals}
