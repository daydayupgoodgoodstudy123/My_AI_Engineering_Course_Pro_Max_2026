"""Three independent finite value-decomposition algorithms; parameters/intake only are supplied."""
from itertools import product
from .models import Monotonicity,JointOracle
from .mix_support import validate_spec,validate_rows,validate_q_values,local_argmax

def mix_joint_value(spec,q_values,features):
    """Evaluate declared state-conditioned hidden affine activations and final affine output."""
    validate_spec(spec,len(q_values),features);validate_q_values(q_values)
    hidden=[]
    for weights,bias,state,activation in zip(spec.hidden_weights,spec.hidden_bias,spec.state_weights,spec.activations):
        value=bias+sum(w*q for w,q in zip(weights,q_values))+sum(w*x for w,x in zip(state,features))
        hidden.append(max(0.,value)if activation=='relu'else value)
    return spec.output_bias+sum(w*x for w,x in zip(spec.output_state,features))+sum(w*x for w,x in zip(spec.output_weights,hidden))

def validate_monotonicity(spec):
    """Give a sufficient nonnegative-weight certificate; failure alone is not an actual greedy counterexample."""
    validate_spec(spec,len(spec.hidden_weights[0])if spec.hidden_weights else 0,(0.,0.))
    bad=[]
    for j,row in enumerate(spec.hidden_weights):
        for i,w in enumerate(row):
            if w<0:bad.append('hidden['+str(j)+']['+str(i)+']')
    for j,w in enumerate(spec.output_weights):
        if w<0:bad.append('output['+str(j)+']')
    return Monotonicity(not bad,tuple(bad))

def joint_action_oracle(spec,rows,features):
    """Enumerate fixed-state Cartesian values and compare greedy VALUE, retaining first declared maximum."""
    validate_rows(rows);validate_spec(spec,len(rows),features)
    greedy=tuple(local_argmax(r)for r in rows)
    greedy_q=tuple(next(x.value for x in r if x.action==a)for r,a in zip(rows,greedy))
    greedy_value=mix_joint_value(spec,greedy_q,features);best=None;count=0
    for selected in product(*rows):
        count+=1;value=mix_joint_value(spec,tuple(x.value for x in selected),features)
        if best is None or value>best[1]:best=tuple(x.action for x in selected),value
    return JointOracle(greedy,greedy_value,best[0],best[1],best[1]-greedy_value,count)
