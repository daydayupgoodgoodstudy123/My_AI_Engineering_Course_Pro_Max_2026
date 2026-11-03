"""Original Phase 13 / Lesson 27 CoderPad practice.

Lesson source: 27-skill-evals-packaging-and-portability/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
def metrics(expected, predicted):
    if len(expected) != len(predicted) or any((type(v) is not bool for v in expected + predicted)):
        raise ValueError('labels')
    tp = sum((a and b for a, b in zip(expected, predicted)))
    fp = sum((not a and b for a, b in zip(expected, predicted)))
    fn = sum((a and (not b) for a, b in zip(expected, predicted)))
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': tp / (tp + fp) if tp + fp else 0.0, 'recall': tp / (tp + fn) if tp + fn else 0.0}

def gate(report, min_precision=0.8, min_recall=0.8):
    reasons = [k for k in ('structure', 'behavior', 'safety', 'portability') if report.get(k) is not True]
    m = report.get('metrics')
    if not isinstance(m, dict) or any((type(m.get(k)) not in (int, float) or not 0 <= m[k] <= 1 for k in ('precision', 'recall'))):
        reasons.append('metrics')
    else:
        if m['precision'] < min_precision:
            reasons.append('precision')
        if m['recall'] < min_recall:
            reasons.append('recall')
    return {'ready': not reasons, 'reasons': sorted(reasons)}

def improvement(baseline, with_skill):
    if any((type(x) not in (int, float) or not 0 <= x <= 1 for x in (baseline, with_skill))):
        raise ValueError('rate')
    return with_skill - baseline
