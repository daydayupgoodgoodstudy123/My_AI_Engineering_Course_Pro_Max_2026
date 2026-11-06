"""Original interview practice for 03-deep-learning-core/01-the-perceptron.

Local source: phases/03-deep-learning-core/01-the-perceptron/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""
import math

def linear(features, weights, bias):
    """weights is a list of output rows, each matching len(features); bias length equals row count. Return dot(row,features)+bias per row. Invalid shapes raise ValueError. Empty output weights and bias yield []."""
    raise NotImplementedError('TODO 1: linear; see PROMPT.md')

def activation(values, kind='relu', slope=0.01):
    """Map numeric values through relu, leaky_relu, or tanh. relu=max(0,x); leaky_relu uses slope*x only for x<0. Unknown kind or negative slope raises ValueError; empty input returns []."""
    raise NotImplementedError('TODO 2: activation; see PROMPT.md')
