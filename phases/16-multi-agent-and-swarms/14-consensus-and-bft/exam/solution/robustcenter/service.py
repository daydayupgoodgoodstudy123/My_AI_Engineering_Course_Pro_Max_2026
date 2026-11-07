"""Complete legacy inspection business; no weighted-position median algorithm is supplied."""
from . import primitives
from .models import Inspection
from .support import ballot_intake,validate_cluster_members,legacy_cluster_scores
class ConfidenceDesk:
    def inspect(self,ballots,threshold,dispersion_limit):
        ballots=ballot_intake(ballots,threshold);groups={};keys=[]
        for ballot in ballots:
            key=primitives.canonicalize_proposal(ballot.proposal.answer)if ballot.proposal.kind=='ANSWER'else None
            groups.setdefault(key,[]).append(ballot);keys.append((ballot.proposal.uid,key))
        validate_cluster_members(groups)
        support=primitives.legacy_support_report(groups,threshold)
        scores=legacy_cluster_scores(groups)
        disagreement=primitives.pairwise_confidence_disagreement(tuple(b.probe.confidence for b in ballots))
        return Inspection(ballots,tuple(keys),support,scores,disagreement,disagreement>dispersion_limit)
