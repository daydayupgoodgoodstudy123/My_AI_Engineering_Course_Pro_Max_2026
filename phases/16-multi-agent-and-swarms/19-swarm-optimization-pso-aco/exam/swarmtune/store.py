"""Candidate complete binary numeric checkpoint and independent deferred routing records."""
from .models import *
from .codec import dumps,loads,pack_vectors,unpack_vectors
from .checkpoint_support import CheckpointMembers
class OptimizerArchive:
    def __init__(self,path):self.driver=CheckpointMembers(path)
    def save(self,checkpoint):
        """Persist complete numeric vectors and domain metadata, full RNG, independent routes, allocations and ordered pending outcomes."""
        raise NotImplementedError
    def load(self):
        """Reconstruct the complete state and explicit delayed arrival records without restarting a seed or deriving one field from another."""
        raise NotImplementedError
    def close(self):self.driver.close()
