"""Five locked parts: shared-family sampled replay and costs; complete JSON configuration;
exact family law; observed-trial TSV; nested joint-family model assembly.
"""
import asyncio
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import csv
import io
import json
import time
import pytest
from corrjury.models import FamilySpec,ReadExposure,JuryConfig,JuryRequest,SeatVote,SampleTally,CostBreakdown,FamilyMass,FamilyProfile,JuryNode
from corrjury.support import ReplayTicketStream
from corrjury.fixture import base_config,replay_fixture
from corrjury.primitives import ticket_outcome,sampled_jury_result,trial_cost
from corrjury.service import JuryDesk
from corrjury.store import JuryArchive
from corrjury.reliability import family_mass_kernel,convolve_family_mass,exact_majority_reliability
from corrjury.wire_support import publish_tsv
from corrjury.stream import trial_fields
from corrjury.structure_support import JuryCatalog
from corrjury.structure import audit_nested_jury

@pytest.mark.skip('Part 1')
def test_shared_draw_strict_majority_read_cost_and_ticket_mapping():
    """Repair family-shared draw provenance, odd-seat strict majority, actual declared read costs and complete varying-config replay work."""
    config=base_config();request=JuryRequest('initial',config);desk=JuryDesk();first=desk.record(request,ReplayTicketStream(5))
    assert len(first.draws)==1 and len(first.votes)==3 and len({v.draw_ordinal for v in first.votes})==1 and len({v.outcome for v in first.votes})==1,'all seats in one family retain one actual shared draw and outcome'
    votes=tuple(SeatVote('seat-'+str(i),'family-'+str(i),i,'RIGHT'if i<2 else'WRONG')for i in range(5))
    assert sampled_jury_result(votes)==SampleTally(2,5,False),'an odd-seat jury requires a strict majority rather than half rounded down'
    assert trial_cost(config)==CostBreakdown(Decimal('0.000600'),Decimal('0.000150'),Decimal('0.000750'),config.reads),'declared peer reading and generation remain separate complete cost components'
    requests,seed,expected=replay_fixture()
    started=time.perf_counter()
    actual=desk.record_many(requests,seed)
    assert actual==expected,'every varying configuration actual roll seat outcome strict result and complete cost report remains intact'
    elapsed=time.perf_counter()-started
    assert elapsed<0.04,'complete varying-config jury replay respects the local response budget'
    for probability in(Fraction(),Fraction(1),Fraction(1,3),Fraction(2,7),Fraction(900003,1000003)):
        legal={0,probability.denominator-1,probability.numerator-1,probability.numerator}
        for roll in sorted(r for r in legal if 0<=r<probability.denominator):
            assert ticket_outcome(probability,roll)==('RIGHT'if Fraction(roll,probability.denominator)<probability else'WRONG'),'every legal boundary roll retains its exact declared Bernoulli category'
    assert len({r.config.families[0].probability for r in requests})==len(requests) and len(actual.trials)==len(requests),'the benchmark contains distinct real probability configurations and retains every trial'
    changed=JuryRequest('changed',replace(config,uid='changed-probability',families=(replace(config.families[0],probability=Fraction(2,7)),)))
    other=desk.record_many((changed,),9281);repeat=desk.record_many(requests,seed);new_seed=desk.record_many(requests,seed+1)
    assert repeat==actual and new_seed.trials[0].draws!=actual.trials[0].draws and other.trials[0].draws[0].denominator==7,'replay observes each supplied configuration and seed without reusing another run outcome'
    zero=desk.record(JuryRequest('zero',replace(config,uid='zero',families=(replace(config.families[0],probability=Fraction()),))),ReplayTicketStream(7))
    sure=desk.record(JuryRequest('sure',replace(config,uid='sure',families=(replace(config.families[0],probability=Fraction(1)),))),ReplayTicketStream(7))
    assert zero.tally==SampleTally(0,3,False) and sure.tally==SampleTally(3,3,True),'zero and unit probabilities retain their deterministic sampled meaning'

@pytest.mark.skip('Part 2')
def test_complete_family_and_exposure_json_snapshot(tmp_path):
    """Persist every ordered family probability/multiplicity and complete distinct generation/read configuration using supplied exact codecs."""
    families=(FamilySpec('family α',Fraction(1,3),3,111),FamilySpec('family β',Fraction(1,10),1,222),FamilySpec('family γ',Fraction(900003,1000003),1,333))
    reads=(ReadExposure('edge-β','peer β','peer α',101),ReadExposure('edge-α','peer α','judge γ',202))
    config=JuryConfig('配置\t完整',families,reads,Decimal('0.00000230'),Decimal('0.00000017'));path=tmp_path/'jury.json'
    archive=JuryArchive(path);archive.save(config);archive.close();reopened=JuryArchive(path);actual=reopened.load();reopened.close()
    assert actual==config,'reopened JSON preserves every declared family probability seat multiplicity and exposure cost setting'
    assert [(f.uid,f.seats,f.generation_tokens)for f in actual.families]==[(f.uid,f.seats,f.generation_tokens)for f in families],'family declarations retain their own order and integer multiplicities without per-seat family copies'
    assert actual.reads==reads and actual.generation_rate==Decimal('0.00000230') and actual.read_rate==Decimal('0.00000017'),'complete reader sender exposure and separate generation/read rates survive reopening'
    document=json.loads(path.read_text())
    assert document['families'][0]['probability']==['1','3'] and document['families'][2]['probability']==['900003','1000003'] and document['generation_rate']=='0.00000230','the supplied scalar codecs retain exact probability and declared decimal text'
    replacement=replace(config,uid='replacement',families=tuple(reversed(families)),reads=tuple(reversed(reads)))
    archive=JuryArchive(path);archive.save(replacement);archive.close();archive=JuryArchive(path)
    assert archive.load()==replacement,'a complete JSON snapshot restores its current full declaration rather than mixing configurations'
    archive.close()
    allocated=replace(config,uid='separate-allocations',reads=(ReadExposure('allocation-1','same reader','same sender',4),ReadExposure('allocation-2','same reader','same sender',9)))
    allocation_path=tmp_path/'allocations.json';allocation_archive=JuryArchive(allocation_path);allocation_archive.save(allocated);allocation_archive.close();allocation_reopened=JuryArchive(allocation_path)
    assert allocation_reopened.load()==allocated,'separate reading allocations survive reopening even when their opaque cost labels coincide'
    allocation_reopened.close()

@pytest.mark.skip('Part 3')
def test_exact_family_kernel_convolution_and_majority_tail(tmp_path):
    """Build family-shared exact kernels, convolve independent families and audit the full strict-majority law from replayed reopened configuration."""
    independent=JuryConfig('independent',(FamilySpec('a',Fraction(1,3),1,100),FamilySpec('b',Fraction(1,3),1,200),FamilySpec('c',Fraction(1,3),1,300)),(ReadExposure('read','a#0','b#0',80),),Decimal('0.000002'),Decimal('0.000001'))
    observed=JuryDesk().record(JuryRequest('actual-replay',independent),ReplayTicketStream(11));archive=JuryArchive(tmp_path/'exact.json');archive.save(observed.config);archive.close();archive=JuryArchive(tmp_path/'exact.json');config=archive.load();archive.close()
    shared=base_config('shared',Fraction(1,3));kernel=family_mass_kernel(shared.families[0])
    assert kernel==FamilyMass('model-family',3,(Fraction(2,3),Fraction(),Fraction(),Fraction(1,3))),'one family moves its complete seat block together in an exact two-point kernel'
    kernels=tuple(family_mass_kernel(family)for family in config.families);distribution=convolve_family_mass(kernels)
    assert distribution==(Fraction(8,27),Fraction(12,27),Fraction(6,27),Fraction(1,27)),'independent family convolution retains the complete exact correct-seat distribution'
    report=exact_majority_reliability(config,distribution)
    assert report.total_seats==3 and report.threshold==2 and report.probability==Fraction(7,27) and report.distribution==distribution,'strict-majority reliability sums only the complete law above the odd-seat threshold'
    shared_report=exact_majority_reliability(shared,convolve_family_mass((kernel,)))
    assert shared_report.probability==Fraction(1,3) and shared_report.probability!=report.probability,'three correlated seats remain one chance rather than three independent Bernoulli trials'
    assert report.cost==observed.cost and report.config_uid==observed.config.uid and sum(distribution,Fraction())==1,'exact reliability consumes the actual reopened configuration and reports corrected costs independently'
    sure=family_mass_kernel(FamilySpec('sure',Fraction(1),3,1));never=family_mass_kernel(FamilySpec('never',Fraction(),1,1))
    assert sure.mass==(Fraction(),Fraction(),Fraction(),Fraction(1)) and never.mass==(Fraction(1),Fraction()),'deterministic families retain exact endpoint masses including zero support entries'
    assert convolve_family_mass(())==(Fraction(1),),'the empty convolution is the exact neutral distribution before adding a family'
    changed=replace(config,reads=config.reads+(ReadExposure('extra','c#0','a#0',900),))
    assert exact_majority_reliability(changed,distribution).probability==report.probability and exact_majority_reliability(changed,distribution).cost.reading>report.cost.reading,'declared communication changes cost without inventing a change in the fixed Bernoulli law'
    with pytest.raises(ValueError,match='complete exact unit-mass'):exact_majority_reliability(config,(Fraction(1,2),Fraction(),Fraction(),Fraction()))
    fixed=JuryConfig('fixed-offset',(FamilySpec('certain',Fraction(1),2,1),FamilySpec('uncertain',Fraction(1,3),1,1)),(),Decimal(0),Decimal(0))
    fixed_distribution=convolve_family_mass(tuple(family_mass_kernel(family)for family in fixed.families))
    assert fixed_distribution==(Fraction(),Fraction(),Fraction(2,3),Fraction(1,3)) and exact_majority_reliability(fixed,fixed_distribution).probability==1,'deterministic families retain their fixed seat offsets in the complete convolved law'

@pytest.mark.skip('Part 4')
def test_actual_trial_fields_and_tsv_observations():
    """Project actual trial/config, supplied family outcomes and observed tally/cost fields without resampling or recomputing classification."""
    base=base_config('错\t配置',Fraction());sure=replace(base_config('sure',Fraction(1)),generation_rate=Decimal('0.000004'),read_rate=Decimal('0.000003'))
    reports=JuryDesk().record_many((JuryRequest('试验\t0',base),JuryRequest('trial-1',sure)),71).trials
    class Source:
        def __init__(self):self.index=0;self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            if self.index==len(reports):raise StopAsyncIteration
            value=reports[self.index];self.index+=1;return value
        async def aclose(self):self.closed=True
    async def collect():
        source=Source();frames=[frame async for frame in publish_tsv(source,trial_fields)];return source,frames
    source,frames=asyncio.run(collect());rows=list(csv.reader(io.StringIO(''.join(frames)),delimiter='\t'))
    assert source.closed and len(rows)==2 and all(len(row)==10 for row in rows),'the supplied TSV publication driver retains complete records and closes its input'
    assert rows[0][:2]==['试验\t0','错\t配置'] and json.loads(rows[0][2])==[['model-family','WRONG']] and rows[0][3:6]==['0','3','False'],'each trial exposes its own identity supplied family outcome and observed strict-majority tally'
    assert rows[1][:2]==['trial-1','sure'] and json.loads(rows[1][2])==[['model-family','RIGHT']] and rows[1][3:6]==['3','3','True'],'later trial evidence remains bound to its own actual configuration and outcome'
    assert rows[0][6:]==['0.0006','0.00015','0.00075','True'] and rows[1][6:]==['0.0012','0.00045','0.00165','True'],'generation reading total and simulated provenance remain distinct observed fields'
    assert trial_fields(reports[1])[0:2]==('trial-1','sure') and trial_fields(reports[1])[-1]is True,'direct domain projection retains the same completed trial observation'

@pytest.mark.skip('Part 5')
def test_nested_family_multiplicities_and_joint_reliability(tmp_path):
    """Assemble every nested jury's global shared-family seat weights and exposures before invoking the repaired exact joint law."""
    config=base_config('earlier',Fraction(1,3));observed=JuryDesk().record(JuryRequest('earlier-trial',config),ReplayTicketStream(4));archive=JuryArchive(tmp_path/'nested.json');archive.save(observed.config);archive.close();archive=JuryArchive(tmp_path/'nested.json');restored=archive.load();archive.close()
    original=restored.families[0];profiles=(FamilyProfile(original.uid,original.probability,original.generation_tokens),FamilyProfile('other',Fraction(2,3),200))
    left_read=ReadExposure('left-read','left-reader','left-sender',10);right_read=ReadExposure('right-read','right-reader','right-sender',20);root_read=ReadExposure('root-read','root-reader','root-sender',30)
    nodes=(JuryNode('left',((original.uid,3),),(left_read,)),JuryNode('right',(('other',3),),(right_read,)),JuryNode('root',((original.uid,1),),(root_read,),('left','right')))
    catalog=JuryCatalog(profiles,nodes,restored.generation_rate,restored.read_rate);audit=audit_nested_jury(catalog.expand('root'),catalog)
    assert audit.family_counts==((original.uid,4),('other',3)) and audit.exact.total_seats==7 and audit.exact.threshold==4,'nested allocations combine every own and child seat into the correct global family blocks'
    assert audit.exact.probability==Fraction(1,3) and audit.exact.distribution==(Fraction(2,9),Fraction(),Fraction(),Fraction(4,9),Fraction(1,9),Fraction(),Fraction(),Fraction(2,9)),'shared causes across branches determine one joint law rather than independent subjury probabilities'
    assert tuple(child.path for child in audit.children)==(('root','left'),('root','right')) and audit.children[0].family_counts==((original.uid,3),) and audit.children[1].family_counts==(('other',3),),'every declared nested layer retains its own ordered model and exact-law audit'
    assert audit.config.reads==(root_read,left_read,right_read) and audit.exact.cost==CostBreakdown(Decimal('0.002'),Decimal('0.00006'),Decimal('0.00206'),(root_read,left_read,right_read)),'nested model composition retains all declared exposures and uses the corrected complete cost dependency'
    assert audit.children[0].exact.probability==Fraction(1,3) and audit.children[1].exact.probability==Fraction(2,3) and audit.exact.probability!=audit.children[0].exact.probability*audit.children[1].exact.probability,'a shared-family parent is not an independent product of its child successes'
    assert audit.config.families[0].probability==restored.families[0].probability and audit.config.uid=='root','nested reliability actually consumes the sampled archived family configuration'
    wrapper_nodes=(JuryNode('voting-child',((original.uid,3),),(left_read,)),JuryNode('observer-wrapper',(),(root_read,),('voting-child',)))
    wrapper_catalog=JuryCatalog(profiles,wrapper_nodes,restored.generation_rate,restored.read_rate);wrapper=audit_nested_jury(wrapper_catalog.expand('observer-wrapper'),wrapper_catalog)
    assert wrapper.path==('observer-wrapper',) and wrapper.config.uid=='observer-wrapper' and wrapper.family_counts==((original.uid,3),) and wrapper.config.reads==(root_read,left_read) and wrapper.exact.probability==Fraction(1,3) and tuple(child.path for child in wrapper.children)==(('observer-wrapper','voting-child'),),'a nonvoting coordination layer retains its own configuration audit and declared reading exposures'
