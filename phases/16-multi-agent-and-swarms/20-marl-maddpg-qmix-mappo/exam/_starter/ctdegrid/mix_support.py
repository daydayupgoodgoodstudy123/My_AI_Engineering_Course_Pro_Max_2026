"""Given finite numeric shape intake and corrected local argmax dependency; no mixing/oracle solver."""
import math
from .world_support import local_argmax

def validate_spec(spec,n,features):
    h=len(spec.hidden_weights)
    if n<1 or h<1 or len(features)!=2 or any(len(r)!=n for r in spec.hidden_weights):raise ValueError('declared mixer dimensions')
    if not(len(spec.hidden_bias)==len(spec.state_weights)==len(spec.activations)==len(spec.output_weights)==h):raise ValueError('hidden dimensions')
    if any(len(r)!=2 for r in spec.state_weights)or len(spec.output_state)!=2 or any(a not in ('identity','relu')for a in spec.activations):raise ValueError('declared state/activation shape')
    values=(*features,*spec.hidden_bias,*spec.output_weights,spec.output_bias,*spec.output_state,*(x for r in spec.hidden_weights for x in r),*(x for r in spec.state_weights for x in r))
    if any(type(x)not in (int,float)or not math.isfinite(x)or abs(x)>1000 for x in values):raise ValueError('bounded finite numeric domain')

def validate_q_values(values):
    if any(type(x)not in (int,float)or not math.isfinite(x)or abs(x)>1000 for x in values):raise ValueError('bounded finite local Q values')

def validate_rows(rows):
    if not rows or any(not r or len({x.action for x in r})!=len(r)for r in rows):raise ValueError('nonempty unique action rows')
    validate_q_values(tuple(x.value for r in rows for x in r))

def training_features(transition):
    return float(transition.before.size),transition.step/(transition.step+1)
