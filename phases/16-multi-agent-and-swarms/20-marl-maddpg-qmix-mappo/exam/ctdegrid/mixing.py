"""Three independent finite value-decomposition algorithms; parameters/intake only are supplied."""
from itertools import product
from .models import Monotonicity,JointOracle
from .mix_support import validate_spec,validate_rows,validate_q_values,local_argmax

def mix_joint_value(spec,q_values,features):
    """Evaluate declared state-conditioned hidden affine activations and final affine output."""
    raise NotImplementedError("Complete the declared domain contract")

def validate_monotonicity(spec):
    """Give a sufficient nonnegative-weight certificate; failure alone is not an actual greedy counterexample."""
    raise NotImplementedError("Complete the declared domain contract")

def joint_action_oracle(spec,rows,features):
    """Enumerate fixed-state Cartesian values and compare greedy VALUE, retaining first declared maximum."""
    raise NotImplementedError("Complete the declared domain contract")
