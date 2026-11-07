"""Candidate domain projections of selected control and explicit terminal records."""
from copy import deepcopy
from .control import resolve_target

class DecisionProjection:
    def decision(self,event):
        """Describe the controlling source, its requested target and the actual message snapshot."""
        mode=event['mode']
        if mode=='static':requested=event['static_next']
        elif mode=='handoff':requested=event['message'].get('handoff','done')
        elif mode=='selector':requested=event['selector_choice']
        else:raise ValueError('local control source')
        target=resolve_target(requested,event['available'])
        outcome='order-complete' if mode=='static' and requested is None else target.kind
        return {'kind':'decision','mode':mode,'step':event['step'],'speaker':event['speaker'],
            'control':{'origin':mode,'requested':requested,'outcome':outcome,'next_agent':target.name if target.kind=='next' else None},'message':deepcopy(event['message'])}

    def stop(self,event):
        """Encode the run's typed stop separately from an agent message or decision."""
        return {'kind':'stop','mode':event['mode'],'reason':event['reason'],'executed':event['executed'],'last_speaker':event['last_speaker']}
