"""Complete replay business orchestration and full audit report; exact reliability solvers remain separate."""
from . import primitives
from .models import TrialReport,BatchReport
from .support import validate_config,ReplayTicketStream,seal_sample,canonical_family_outcomes,money_sum
class JuryDesk:
    def record(self,request,stream):
        config=validate_config(request.config);cursor=stream.cursor
        votes=primitives.draw_family_trial(config,stream)
        votes,draws=seal_sample(config,votes,stream.since(cursor))
        tally=primitives.sampled_jury_result(votes);cost=primitives.trial_cost(config)
        return TrialReport(request.trial_id,config,draws,votes,canonical_family_outcomes(config,votes),tally,cost)
    def record_many(self,requests,seed):
        requests=tuple(requests);stream=ReplayTicketStream(seed);trials=tuple(self.record(request,stream)for request in requests)
        return BatchReport(requests,trials,sum(t.tally.passed for t in trials),money_sum(t.cost.generation for t in trials),money_sum(t.cost.reading for t in trials),money_sum(t.cost.total for t in trials))
