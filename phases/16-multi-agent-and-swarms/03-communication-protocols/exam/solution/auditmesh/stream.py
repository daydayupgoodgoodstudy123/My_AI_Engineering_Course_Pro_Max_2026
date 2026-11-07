"""Synchronous audit-domain accumulation and terminal projection; driver is GIVEN."""
from copy import deepcopy
from .gateway import public_step
from .value_codec import same_value

class AuditProjection:
    def __init__(self,run_id,policy):
        self.run_id=run_id;self.policy=policy;self._steps=[];self._sealed=False

    def on_step(self,run_id,step):
        """Retain every observed slot and export only this policy-selected observation."""
        if self._sealed:raise ValueError('audit already sealed')
        if run_id!=self.run_id:raise ValueError('audit run mismatch')
        slot=len(self._steps)
        self._steps.append(deepcopy(step))
        return 'audit-step',{'run_id':self.run_id,'slot':slot,'observation':public_step(step,self.policy)}

    def on_seal(self,receipt):
        """Seal exactly the observed trajectory; preserve failed outcome/error/completion time."""
        if self._sealed:raise ValueError('audit already sealed')
        if receipt['run_id']!=self.run_id:raise ValueError('audit run mismatch')
        if not same_value(receipt['trajectory'],self._steps):raise ValueError('sealed trajectory differs from observed slots')
        if receipt['status'] not in ('completed','failed'):raise ValueError('audit not terminal')
        self._sealed=True
        result={key:deepcopy(receipt[key]) for key in ('run_id','agent','session_id','status','started_at','completed_at','error')}
        result['trajectory_count']=len(self._steps)
        return 'audit-sealed',result

    def finish(self):
        """A completed source must include its terminal receipt, even for zero steps."""
        if not self._sealed:raise ValueError('audit source ended without seal')
