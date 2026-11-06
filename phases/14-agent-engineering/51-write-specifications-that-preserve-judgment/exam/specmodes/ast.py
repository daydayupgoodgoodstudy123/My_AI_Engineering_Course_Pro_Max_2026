"""Finite structured limits, not a natural-language specification parser."""
from __future__ import annotations
import math

def validate_ast(node) -> None:
    """Supplied finite schema, at most 20 nested groups in valid inputs. A node is
    {'all': [nodes]} / {'any':[nodes]} (nonempty), or {'limit':{metric,max,unit}}, or
    {'allowed':{metric,values}}. Limits use sources/retries (unit '') or elapsed (s/ms);
    exact allowlists use dependency/interface. Empty groups/unknown metrics invalid.
    """
    if not isinstance(node,dict) or len(node)!=1:raise ValueError('invalid boundary AST')
    kind,value=next(iter(node.items()))
    if kind in ('all','any'):
        if not isinstance(value,list) or not value:raise ValueError('empty boundary group')
        for child in value:validate_ast(child)
    elif kind=='limit':
        metric=value['metric'];maximum=value['max'];unit=value.get('unit','')
        if (metric not in ('sources','retries','elapsed') or type(maximum) not in (int,float)
            or not math.isfinite(maximum) or maximum<=0 or (unit not in ('s','ms') if metric=='elapsed' else unit!='')):
            raise ValueError('invalid limit')
    elif kind=='allowed':
        if value['metric'] not in ('dependency','interface') or not value['values'] or any(not v.strip() for v in value['values']):raise ValueError('invalid allowlist')
    else:raise ValueError('unknown boundary node')

def leaf_allowed(kind: str,value: dict,context: dict) -> bool:
    """Supplied unit conversion and strict next-action limit semantics."""
    if kind=='allowed':return context[value['metric']] in value['values']
    maximum=value['max']/1000 if value['metric']=='elapsed' and value.get('unit')=='ms' else value['max']
    return context[value['metric']]<maximum

def evaluate_boundary(node,context: dict) -> dict:
    """Return {'allowed': bool, 'blocked': tuple-of-index-paths}. Leaf root path is
    (). ALL permits only if all children permit and reports every blocking child leaf
    in depth-first order. ANY permits if at least one child permits; a passing ANY
    hides all failed sibling paths. A failing ANY reports all its blocking leaf paths.
    Paths use child indexes from the root, not metric names; repeated metrics remain
    distinct occurrences. Use supplied schema/leaf helpers; no mutation.
    """
    raise NotImplementedError
