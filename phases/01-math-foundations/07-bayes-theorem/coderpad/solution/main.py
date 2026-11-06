"""Original interview practice for 01-math-foundations/07-bayes-theorem.

Local source: phases/01-math-foundations/07-bayes-theorem/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def bayes(prior, likelihood_positive, likelihood_negative):
    if any((not 0 <= x <= 1 for x in (prior, likelihood_positive, likelihood_negative))):
        raise ValueError('probability')
    den = prior * likelihood_positive + (1 - prior) * likelihood_negative
    if den == 0:
        raise ValueError('impossible evidence')
    return prior * likelihood_positive / den

def classification(expected, predicted):
    if len(expected) != len(predicted) or any((type(x) is not bool for x in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    tn = len(expected) - tp - fp - fn
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'precision': p, 'recall': r, 'f1': 2 * p * r / (p + r) if p + r else 0}
