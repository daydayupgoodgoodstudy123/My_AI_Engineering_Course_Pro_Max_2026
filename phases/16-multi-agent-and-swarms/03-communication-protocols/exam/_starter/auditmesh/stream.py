"""Synchronous audit-domain accumulation and terminal projection; driver is GIVEN."""
from copy import deepcopy
from .gateway import public_step
from .value_codec import same_value

class AuditProjection:
    def __init__(self,run_id,policy):
        self.run_id=run_id;self.policy=policy;self._steps=[];self._sealed=False

    def on_step(self,run_id,step):
        """Retain every observed slot and export only this policy-selected observation."""
        raise NotImplementedError

    def on_seal(self,receipt):
        """Seal exactly the observed trajectory; preserve failed outcome/error/completion time."""
        raise NotImplementedError

    def finish(self):
        """A completed source must include its terminal receipt, even for zero steps."""
        raise NotImplementedError
