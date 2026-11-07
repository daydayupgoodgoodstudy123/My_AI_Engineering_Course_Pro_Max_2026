"""Five locked parts: signed clusters and confidence dispersion; complete proposal/probe
snapshots; weighted scalar median intervals; framed proposal evidence; Core/Edge audit trees.
"""
import asyncio
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import json
import struct
import time
import pytest
from robustcenter.models import NumericKey,ClusterSupport,WeightedPosition,MedianInterval,TruthLabel,CenterAudit,CoreGroup,EdgeAck,EdgeAudit
from robustcenter.fixture import ballot,inspection_fixture
from robustcenter.primitives import canonicalize_proposal,pairwise_confidence_disagreement
from robustcenter.service import ConfidenceDesk
from robustcenter.store import ProposalArchive
from robustcenter.scalar_support import positions_from_inspection
from robustcenter.center import weighted_median_interval,choose_interval_center,audit_center_support
from robustcenter.wire_support import public_observation,publish_frames
from robustcenter.stream import proposal_payload
from robustcenter.certificate_support import seal_core,CoreCatalog
from robustcenter.certificate import audit_core_tree

@pytest.mark.skip('Part 1')
def test_signed_clusters_abstentions_mass_and_dispersion():
    """Repair signed proposal grouping, explicit abstention admission, confidence-mass thresholds and complete dispersion work."""
    desk=ConfidenceDesk();negative=ballot('negative','-4.2%',Fraction(2,3));positive=ballot('positive','4.2%',Fraction(1,3))
    signed=desk.inspect((negative,positive),Fraction(2,3),Fraction(10))
    assert signed.canonical==(('negative',NumericKey(Decimal('-4.2'),'percent')),('positive',NumericKey(Decimal('4.2'),'percent'))),'opposite signed proposals remain distinct numeric claims'
    abstain=ballot('abstain',None,Fraction(1),kind='ABSTAIN');answer=ballot('answer','4.2%',Fraction(1,5))
    report=desk.inspect((abstain,answer),Fraction(2,3),Fraction(10));key=NumericKey(Decimal('4.2'),'percent')
    assert report.support==ClusterSupport(((key,Fraction(1,5)),),Fraction(1,5),key,('abstain',)),'abstentions retain their evidence without acquiring answer support or denominator mass'
    majority=(ballot('strong','4.2%',Fraction(9,10)),ballot('weak-a','42%',Fraction(1,10)),ballot('weak-b','42%',Fraction(1,10)),ballot('weak-c','42%',Fraction(1,10)))
    weighted=desk.inspect(majority,Fraction(3,5),Fraction(10))
    assert weighted.support.winner==key and weighted.support.total==Fraction(6,5),'declared confidence mass determines admission even when member counts disagree'
    records,threshold,limit,expected=inspection_fixture()
    started=time.perf_counter()
    inspection=desk.inspect(records,threshold,limit)
    assert inspection==expected,'every proposal probe canonical cluster legacy score and dispersion field remains complete'
    elapsed=time.perf_counter()-started
    assert elapsed<0.15,'complete confidence inspection respects the local response budget'
    assert canonicalize_proposal(' -4,20 percent ')==NumericKey(Decimal('-4.20'),'percent') and canonicalize_proposal('4.2')!=key,'declared decimal variants retain their signed value and physical unit'
    assert pairwise_confidence_disagreement((Fraction(),Fraction(),Fraction(),Fraction(1)))==3 and pairwise_confidence_disagreement((Fraction(),Fraction(),Fraction(1),Fraction(1)))==4,'pairwise dispersion retains multiplicity beyond the extreme confidence gap'
    assert pairwise_confidence_disagreement(())==0 and pairwise_confidence_disagreement((Fraction(1,7),))==0,'zero or one confidence has no unordered pair disagreement'
    no_mass=desk.inspect((ballot('zero','4.2%',0),abstain),Fraction(1),Fraction(10))
    assert no_mass.support.winner is None and no_mass.support.total==0 and no_mass.ballots[-1]==abstain,'zero eligible mass cannot be admitted while all declared evidence remains visible'
    assert signed.support.winner==NumericKey(Decimal('-4.2'),'percent') and signed.support.total==1,'the declared inclusive confidence threshold accepts its exact boundary'

@pytest.mark.skip('Part 2')
def test_complete_proposal_and_independent_probe_snapshots(tmp_path):
    """Model full ordered proposal snapshots and actual independent probes, then close and reopen their original evidence."""
    first=ballot('original','-4,2 percent',Fraction(1,3),Fraction(9,10),evaluator='reviewer α')
    retry=replace(ballot('retry','4.25%',Fraction(2**54+7,2**55+19),Fraction(2,7),evaluator='reviewer β'),proposal=replace(first.proposal,uid='retry',answer='4.25%',self_confidence=Fraction(2,7)))
    abstain=ballot('decline',None,Fraction(5,7),Fraction(),kind='ABSTAIN',evaluator='reviewer 中文')
    records=(first,retry,abstain);path=tmp_path/'proposals.sqlite'
    archive=ProposalArchive(path);archive.save('run-α',records);archive.save('other',(retry,));archive.close()
    reopened=ProposalArchive(path);actual=reopened.load('run-α')
    assert actual==records,'reopened snapshots retain every original proposal and independent probe field in declaration order'
    assert actual[0].proposal.agent==actual[1].proposal.agent and [b.proposal.uid for b in actual]==['original','retry','decline'],'distinct retries from one agent retain their own immutable evidence identities'
    assert actual[0].probe.confidence==Fraction(1,3) and actual[0].proposal.self_confidence==Fraction(9,10) and actual[0].probe.evaluator=='reviewer α','independent probe evidence remains separate from proposal self-confidence'
    rows=reopened._database.db.execute('SELECT proposal_uid,probe_uid,confidence_n,confidence_d,evaluator,assessment FROM probes WHERE run=? ORDER BY ordinal',('run-α',)).fetchall()
    assert rows==[(b.probe.proposal_uid,b.probe.probe_uid,str(b.probe.confidence.numerator),str(b.probe.confidence.denominator),b.probe.evaluator,b.probe.assessment)for b in records],'stored probe rows contain the actual bound evaluator records without substituted fields'
    reopened.save('run-α',(abstain,first));reopened.close();final=ProposalArchive(path)
    assert final.load('run-α')==(abstain,first) and final.load('other')==(retry,),'a full snapshot replaces only its own run and retains the other run intact'
    assert final.load('absent')==() and actual[2].proposal.answer is None and actual[1].probe.confidence==retry.probe.confidence,'the supplied schema and exact codec preserve typed absent answers and declared rational evidence'
    final.close()
    zero_probe=ballot('zero-probe','4.2%',Fraction(),Fraction(4,5))
    external_probe=replace(first,probe=replace(first.probe,probe_uid='evaluation:α:run-7'))
    evidence_archive=ProposalArchive(tmp_path/'evidence.sqlite');evidence_archive.save('zero-mass',(zero_probe,));evidence_archive.save('actual-probe',(external_probe,));evidence_archive.close()
    evidence_reopened=ProposalArchive(tmp_path/'evidence.sqlite')
    assert evidence_reopened.load('zero-mass')==(zero_probe,),'zero-mass proposals retain complete original audit evidence after reopening'
    assert evidence_reopened.load('actual-probe')==(external_probe,),'reopening preserves the actual independent probe identity without inventing a naming convention'
    evidence_reopened.close()

@pytest.mark.skip('Part 3')
def test_weighted_median_interval_ties_and_radius_support(tmp_path):
    """Compute the full weighted-median interval, requested tie point and exact radius support from reopened inspected evidence."""
    records=(ballot('low','0%',Fraction(2,3)),ballot('middle','10%',Fraction(1,3)),ballot('outlier','100%',Fraction(1,3)),ballot('ignored','-999%',0))
    archive=ProposalArchive(tmp_path/'positions.sqlite');archive.save('positions',records);archive.close();archive=ProposalArchive(tmp_path/'positions.sqlite')
    inspection=ConfidenceDesk().inspect(archive.load('positions'),Fraction(2,3),Fraction(100));archive.close();points=positions_from_inspection(inspection)
    interval=weighted_median_interval(points)
    assert interval==MedianInterval(Decimal(0),Decimal(10),'percent'),'exact half mass retains the complete adjacent positive-position minimizer interval'
    lower=choose_interval_center(interval,'lower');upper=choose_interval_center(interval,'upper');middle=choose_interval_center(interval,'midpoint')
    assert (lower,upper,middle)==(Decimal(0),Decimal(10),Decimal(5)),'the requested interval tie policy determines the reported scalar center'
    audit=audit_center_support(points,middle,Fraction(5),Fraction(3,4),TruthLabel(Decimal(5),'percent'))
    assert audit==CenterAudit(Decimal(5),'percent',Fraction(1),Fraction(4,3),True,('outlier',),True),'inclusive radius support retains exact masses and ordered minority proposal provenance'
    assert audit_center_support(points,middle,Fraction(5),Fraction(3,4)).truth is None and audit_center_support(points,middle,Fraction(5),Fraction(3,4),TruthLabel(Decimal(100),'percent')).truth is False,'supplied independent truth remains separate from agreement admission'
    dominant=(WeightedPosition('outlier',Decimal(999),'scalar',Fraction(1,10)),WeightedPosition('center',Decimal(2),'scalar',Fraction(9,10)))
    assert weighted_median_interval(dominant)==MedianInterval(Decimal(2),Decimal(2),'scalar'),'large position distance does not replace confidence mass with an arithmetic mean'
    duplicates=(WeightedPosition('a',Decimal(0),'scalar',Fraction(1,4)),WeightedPosition('b',Decimal(0),'scalar',Fraction(1,4)),WeightedPosition('c',Decimal(10),'scalar',Fraction(1,2)))
    assert weighted_median_interval(duplicates)==MedianInterval(Decimal(0),Decimal(10),'scalar'),'equal-valued proposals retain their complete positive confidence mass'
    reversed_points=tuple(reversed(points));strict=audit_center_support(reversed_points,Decimal(0),Fraction(0),Fraction(2,3))
    assert not strict.accepted and strict.minority==('outlier','middle'),'minority evidence follows original declaration order while radius support uses actual mass'
    with pytest.raises(ValueError,match='positive total mass'):weighted_median_interval((WeightedPosition('zero',Decimal(0),'scalar',Fraction()),))
    zero_between=(WeightedPosition('left',Decimal(0),'scalar',Fraction(1,2)),WeightedPosition('massless',Decimal(5),'scalar',Fraction()),WeightedPosition('right',Decimal(10),'scalar',Fraction(1,2)))
    assert weighted_median_interval(zero_between)==MedianInterval(Decimal(0),Decimal(10),'scalar'),'zero-mass interior positions do not shorten the positive-mass minimizer interval'

@pytest.mark.skip('Part 4')
def test_each_proposal_numeric_and_probe_evidence_frames():
    """Project each proposal's own signed scalar/unit, original text and self-report beside supplied independent probe evidence."""
    records=(ballot('first','-4,20 percent',Fraction(1,3),Fraction(9,10),evaluator='评估 α'),ballot('second','4.2',Fraction(3,7),Fraction(1,5)),ballot('abstain',None,Fraction(5,7),kind='ABSTAIN'))
    class Source:
        def __init__(self):self.index=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index==len(records):raise StopAsyncIteration
            value=records[self.index];self.index+=1;return value
        async def aclose(self):self.closed=True
    async def collect():
        source=Source();frames=[frame async for frame in publish_frames(source,proposal_payload)];return source,frames
    source,frames=asyncio.run(collect());decoded=[json.loads(frame[4:])for frame in frames]
    assert source.closed and all(struct.unpack('!I',frame[:4])[0]==len(frame[4:])for frame in frames),'the supplied framed publication driver preserves complete payloads and closes its source'
    assert decoded[0]=={'kind':'ANSWER','proposal_uid':'first','agent':'agent-first','answer':'-4,20 percent','position':'-4.20','unit':'percent','self_confidence':['9','10'],'probe_uid':'probe-first','probe_confidence':['1','3'],'evaluator':'评估 α','assessment':'declared fixture probe'},'proposal evidence retains its own signed position original text and complete evaluator association'
    assert decoded[1]['proposal_uid']=='second' and decoded[1]['agent']=='agent-second' and decoded[1]['position']=='4.2' and decoded[1]['unit']=='scalar' and decoded[1]['self_confidence']==['1','5'],'each later proposal retains its own identity scalar unit and self-report'
    assert decoded[2]['kind']=='ABSTAIN' and decoded[2]['answer']is None and decoded[2]['position']is None and decoded[2]['unit']is None and decoded[2]['probe_confidence']==['5','7'],'the supplied abstention projection preserves non-voting probe evidence without a fabricated numeric claim'
    assert proposal_payload(public_observation(records[1]))==decoded[1],'direct domain projection matches the same proposal observed through framed publication'

@pytest.mark.skip('Part 5')
def test_nested_core_and_edge_following_certificates(tmp_path):
    """Build each nested core's own sealed-decision and EdgeAck audit; evidence admission and independent truth are supplied."""
    archive=ProposalArchive(tmp_path/'cores.sqlite')
    root_records=(ballot('root-a','0%',Fraction(1,2)),ballot('root-b','10%',Fraction(1,2)))
    child_records=(ballot('child-a','20%',Fraction(1,2)),ballot('child-b','22%',Fraction(1,2)))
    archive.save('root',root_records);archive.save('child',child_records);archive.close();archive=ProposalArchive(tmp_path/'cores.sqlite')
    desk=ConfidenceDesk();root_inspection=desk.inspect(archive.load('root'),Fraction(1,2),Fraction(10));child_inspection=desk.inspect(archive.load('child'),Fraction(1,2),Fraction(10));archive.close()
    root=seal_core('core/root',8,root_inspection,'midpoint',Fraction(5),Fraction(1));child=seal_core('core/child',13,child_inspection,'midpoint',Fraction(1),Fraction(1));rejected=seal_core('core/rejected',3,root_inspection,'midpoint',Fraction(),Fraction(2,3))
    catalog=CoreCatalog((root,child,rejected))
    good=EdgeAck('good','core/root',8,Decimal(5),'percent',('root-a',));wrong_parent=EdgeAck('wrong-parent','core/child',13,Decimal(21),'percent',('child-a',));stale=replace(good,edge_uid='stale',epoch=7);wrong_value=replace(good,edge_uid='wrong-value',center=Decimal(6));unknown=replace(good,edge_uid='unknown',references=('missing',))
    child_edge=EdgeAck('child-edge','core/child',13,Decimal(21),'percent',('child-b',));rejected_edge=EdgeAck('rejected-edge','core/rejected',3,Decimal(5),'percent',('root-a',))
    nested=CoreGroup('core/child',13,Decimal(21),'percent',(child_edge,));refused=CoreGroup('core/rejected',3,Decimal(5),'percent',(rejected_edge,));tree=CoreGroup('core/root',8,Decimal(5),'percent',(good,wrong_parent,stale,wrong_value,unknown),(nested,refused))
    audit=audit_core_tree(tree,catalog)
    assert audit.path==('core/root',) and audit.sealed==root and audit.findings==() and audit.edges[0]==EdgeAudit('good',()),'an accepted core retains its actual earlier-part sealed decision and matching own EdgeAck'
    assert audit.edges[1].findings==('edge-parent','edge-epoch','edge-value') and audit.edges[2].findings==('edge-epoch',) and audit.edges[3].findings==('edge-value',) and audit.edges[4].findings==('edge-reference',),'each edge follows the current core identity epoch value and supplied original-evidence binding'
    assert audit.children[0].path==('core/root','core/child') and audit.children[0].sealed==child and audit.children[0].edges==(EdgeAudit('child-edge',()),),'nested child cores retain their own independent sealed state and ordered local edge reports'
    assert audit.children[1].findings==('core-not-accepted',) and audit.children[1].edges[0].findings==('edge-before-core',),'an edge cannot supply admission for an unaccepted original core'
    changed=audit_core_tree(replace(tree,epoch=9,claimed_center=Decimal(6),children=()),catalog)
    assert changed.findings==('core-epoch','core-value') and changed.edges[0].findings==(),'core snapshot disagreements remain distinct from an edge matching the sealed decision'
    assert root.decision.truth is None and child.decision.truth is None and rejected.decision.support==0 and root.decision.support==1,'supplied truth and original support do not acquire additional evidence from following edges'
