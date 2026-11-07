"""Model complete proposal and actual independent probe snapshots, preserving original field provenance."""
from .models import Proposal,Probe,Ballot
from .database_support import Database,encode_fraction,decode_fraction
class ProposalArchive:
    def __init__(self,path):self._database=Database(path)
    def save(self,run,ballots):
        """Persist every proposal and its actual independent probe, never substitute self-confidence."""
        proposals=[];probes=[]
        for index,ballot in enumerate(ballots):
            p=ballot.proposal;q=ballot.probe
            proposals.append((index,p.uid,p.agent,p.kind,p.answer,*encode_fraction(p.self_confidence)))
            probes.append((index,q.proposal_uid,q.probe_uid,*encode_fraction(q.confidence),q.evaluator,q.assessment))
        self._database.replace(run,proposals,probes)
    def load(self,run):
        """Reopen all ordered proposals and complete original evaluator evidence without inventing another probe."""
        proposals,probes=self._database.rows(run);restored=[]
        for p,q in zip(proposals,probes):
            restored.append(Ballot(Proposal(p[1],p[2],p[3],p[4],decode_fraction(p[5],p[6])),Probe(q[1],q[2],decode_fraction(q[3],q[4]),q[5],q[6])))
        return tuple(restored)
    def close(self):self._database.close()
