"""Five locked parts: standing-offer clearing and numeric display; dual continuation journals;
own concession and bounded mechanism; public numeric/narrative events; nested joint feasibility.
"""
import asyncio
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import json
import time
import pytest
from bargainkit.models import Strategy,Quote,Narration,PublicOffer,Settlement,SuppliedRequest,BargainState,SavedBargain,PolicyInput,PublicEvent,UtilityRule,PartyUtility,OfferTerm,OfferGroup
from bargainkit.primitives import count_price_ticks,public_offer_view
from bargainkit.exact import amount_atoms
from bargainkit.service import OfferDesk
from bargainkit.fixture import pair,review_fixture
from bargainkit.store import BargainArchive
from bargainkit.mechanism_support import buyer_input,seller_input
from bargainkit.mechanism import next_buyer_offer,next_seller_offer,run_bargain
from bargainkit.wire_support import NarrationCatalog,public_events,publish_events
from bargainkit.stream import event_fields
from bargainkit.structure_support import OfferCatalog,public_blocker
from bargainkit.structure import audit_offer_tree

def initial_saved(uid='bargain'):
    buyer=Strategy('buyer','buyer',Decimal('100'),Decimal('0'),Fraction(1,2))
    seller=Strategy('seller','seller',Decimal('50'),Decimal('100'),Fraction(1,2))
    return SavedBargain(uid,BargainState(uid,'cpu',Decimal('1')),buyer,seller)

def archived_run(tmp_path,uid='integrated'):
    saved=initial_saved(uid);public=OfferDesk().evaluate_supplied(SuppliedRequest(Quote(uid+'/opening',uid,'cpu',1,0,'buyer',Decimal('0'),Decimal('1')),None,saved.buyer,saved.seller)).public
    half=replace(saved,state=replace(saved.state,revision=1,next_side='seller',buyer_quote=public.quote),offers=(public,))
    archive=BargainArchive(tmp_path/uid);archive.save(half);archive.close();archive=BargainArchive(tmp_path/uid);restored=archive.load(uid);archive.close()
    return run_bargain(restored,10)

@pytest.mark.skip('Part 1')
def test_standing_clearing_inclusive_private_text_and_real_tick_encoding():
    """Repair standing-price clearing, inclusive feasible endpoints, public-only narration and complete real numeric batch encoding."""
    buyer,seller=pair();desk=OfferDesk();bid=Quote('bid','n','cpu',2,1,'buyer',Decimal('1000.00'),Decimal('0.01'));ask=replace(bid,uid='ask',revision=1,side='seller',price=Decimal('900.00'))
    receipt=desk.evaluate_supplied(SuppliedRequest(bid,ask,buyer,seller))
    assert receipt.settlement==Settlement('n','cpu','ask',Decimal('900.00')) and receipt.buyer_surplus==Decimal('600') and receipt.seller_surplus==Decimal('200'),'a crossed bid settles at its referenced standing ask with both actual surpluses'
    singleton_b=replace(buyer,reservation=Decimal('100'),opening=Decimal('100'));singleton_s=replace(seller,reservation=Decimal('100'),opening=Decimal('100'));edge=replace(bid,price=Decimal('100'),tick=Decimal('1'));standing=replace(edge,uid='single-ask',side='seller')
    assert desk.evaluate_supplied(SuppliedRequest(edge,standing,singleton_b,singleton_s)).settlement is not None,'a singleton feasible price remains an inclusive deal'
    assert receipt.public.narration==Narration('bid',2,'buyer offers 1000.00 USD'),'public narration contains the actual offer rather than a private strategy value'
    requests,expected=review_fixture();started=time.perf_counter();actual=desk.review_many(requests)
    assert actual==expected,'every supplied request standing-price receipt surplus public quote narration and both tick counts remain complete'
    elapsed=time.perf_counter()-started
    assert elapsed<0.04,'complete numeric bargaining review respects the local response budget'
    assert count_price_ticks(0,7)==0 and count_price_ticks(1,1)==1 and count_price_ticks(42,7)==6 and count_price_ticks(35,5)==7,'zero one and nonunit grids retain their exact integer unit counts'
    with pytest.raises(ValueError,match='tick grid'):count_price_ticks(43,7)
    opposite=replace(bid,uid='ask-in',side='seller',price=Decimal('850'));standing_bid=replace(opposite,uid='standing-bid',side='buyer',price=Decimal('925'))
    assert desk.evaluate_supplied(SuppliedRequest(opposite,standing_bid,buyer,seller)).settlement.price==Decimal('925'),'a crossed ask retains the counterpart standing bid price'
    assert desk.evaluate_supplied(SuppliedRequest(replace(bid,price=Decimal('899')),ask,buyer,seller)).settlement is None and desk.evaluate_supplied(SuppliedRequest(bid,None,buyer,seller)).settlement is None,'a noncrossing quote and an opening quote remain unsettled'
    assert public_offer_view(replace(bid,uid='other',revision=9,price=Decimal('1000.25')),buyer).price_ticks==100025 and actual.receipts[-1].public.quote.uid==requests[-1].incoming.uid,'numeric encoding observes each current quote and preserves every actual request identity'

@pytest.mark.skip('Part 2')
def test_private_continuation_and_ordered_public_dual_journals(tmp_path):
    """Persist complete own checkpoint phase, both standing slots, private strategies and linked public history through supplied exact separate-channel codecs."""
    saved=initial_saved('续接');desk=OfferDesk();q1=Quote('bid-old','续接','cpu',1,0,'buyer',Decimal('0.00'),Decimal('0.01'));q2=replace(q1,uid='ask-old',revision=2,side='seller',price=Decimal('90.00'))
    p1=desk.evaluate_supplied(SuppliedRequest(q1,None,saved.buyer,saved.seller)).public;p2=desk.evaluate_supplied(SuppliedRequest(q2,q1,saved.buyer,saved.seller)).public
    saved=replace(saved,state=replace(saved.state,tick=Decimal('0.01'),round=3,revision=2,next_side='buyer',buyer_quote=q1,seller_quote=q2),offers=(p2,p1,p1),buyer=replace(saved.buyer,party='private buyer',concession=Fraction(2,7)))
    other_bid=replace(q1,uid='other-bid',negotiation_id='other',revision=4,price=Decimal('100.00'));other_ask=replace(q2,uid='other-ask',negotiation_id='other',revision=3);other_public=desk.evaluate_supplied(SuppliedRequest(other_bid,other_ask,saved.buyer,saved.seller)).public;other_standing=desk.evaluate_supplied(SuppliedRequest(other_ask,None,saved.buyer,saved.seller)).public
    other=replace(saved,checkpoint_uid='other',state=replace(saved.state,negotiation_id='other',round=7,revision=4,buyer_quote=other_bid,seller_quote=other_ask,closed='deal',settlement=Settlement('other','cpu','other-ask',Decimal('90.00'))),offers=(other_standing,other_public))
    archive=BargainArchive(tmp_path);archive.save(saved);archive.save(other);archive.close();archive=BargainArchive(tmp_path);restored=archive.load('续接');second=archive.load('other');public=archive.public_history('续接');archive.close()
    assert restored==saved and second==other,'reopening each checkpoint retains its complete independent bargaining continuation'
    assert restored.state.buyer_quote==q1 and restored.state.seller_quote==q2 and restored.state.round==3 and restored.state.next_side=='buyer','both own standing slots and the next alternating phase remain distinct'
    assert public==(p2,p1,p1) and restored.buyer.concession==Fraction(2,7) and restored.buyer.party=='private buyer' and str(restored.state.tick)=='0.01' and str(restored.state.buyer_quote.price)=='0.00','ordered repeated public observations and exact private strategy settings survive reopening'
    rows=[json.loads(line)for line in(tmp_path/'public.jsonl').read_text().splitlines()]
    assert set(rows[0]['value'][0])=={'quote','narration','price_ticks'} and 'buyer'not in rows[0]['value'][0] and 'seller'not in rows[0]['value'][0],'the supplied public channel persists typed public offers rather than private strategy documents'
    replacement=replace(saved,state=replace(saved.state,round=4,next_side='seller'),offers=(p1,p2));archive=BargainArchive(tmp_path);archive.save(replacement);archive.close();archive=BargainArchive(tmp_path)
    assert archive.load('续接')==replacement and archive.load('other')==other,'the latest complete checkpoint replaces its own continuation without mixing another checkpoint'
    archive.close()

@pytest.mark.skip('Part 3')
def test_directional_concession_tick_progress_and_bounded_resume(tmp_path):
    """Compute own directed gaps and fractional tick concessions, preserve feasible progress/reservations, and resume actual archived alternating turns."""
    b=PolicyInput(Decimal('1.00'),True,Decimal('1.15'),Decimal('2.00'),Decimal('0.05'),Fraction(1,2));s=PolicyInput(Decimal('2.00'),True,Decimal('1.85'),Decimal('1.00'),Decimal('0.05'),Fraction(1,2))
    assert next_buyer_offer(b)==Decimal('1.05') and next_seller_offer(s)==Decimal('1.95') and next_buyer_offer(replace(b,concession=Decimal('0.5')))==Decimal('1.05'),'each side applies its own directed fractional concession on the declared tick grid'
    assert next_buyer_offer(replace(b,counter=Decimal('1.05'),concession=Fraction(1,10)))==Decimal('1.05') and next_seller_offer(replace(s,counter=Decimal('1.95'),concession=Fraction(1,10)))==Decimal('1.95'),'a positive feasible gap retains at least one tick of progress'
    assert next_buyer_offer(replace(b,reservation=Decimal('1.10'),counter=Decimal('3.00'),concession=Fraction(1)))==Decimal('1.10') and next_seller_offer(replace(s,reservation=Decimal('1.90'),counter=Decimal('0'),concession=Fraction(1)))==Decimal('1.90'),'both directions stop at their own reservation rather than crossing their private limit'
    assert next_buyer_offer(replace(b,counter=Decimal('0.50')))==b.base and next_seller_offer(replace(s,counter=Decimal('2.50')))==s.base and next_buyer_offer(replace(b,has_counter=False))==b.base,'an absent or already favorable counterquote does not reverse an own standing offer'
    result=archived_run(tmp_path);settlement=result.saved.state.settlement
    assert result.status=='deal' and settlement.price==Decimal('50') and result.saved.state.closed=='deal','the bounded mechanism consumes an actual supplied public opening and reopened private continuation'
    assert result.new_offers[0].quote.side=='seller' and result.new_offers[-1].quote.side=='buyer' and len(result.new_offers)==14 and result.saved.state.round==7,'resuming a half round preserves its declared next side and stops on the first completed deal'
    assert all(left.quote.side!=right.quote.side for left,right in zip(result.new_offers,result.new_offers[1:])) and run_bargain(result.saved,20).new_offers==(),'the mechanism alternates actual turns and emits no additional offer from a closed checkpoint'
    short=run_bargain(initial_saved('short'),1);impossible=initial_saved('no-zopa');impossible=replace(impossible,seller=replace(impossible.seller,reservation=Decimal('110'),opening=Decimal('120')))
    assert short.status=='exhausted' and len(short.new_offers)==2 and short.saved.state.round==1 and run_bargain(impossible,10).status=='no-zopa' and not run_bargain(impossible,10).new_offers,'the total round ceiling and an empty feasible interval remain explicit nondeal outcomes'
    assert buyer_input(result.saved).reservation==result.saved.buyer.reservation and seller_input(result.saved).reservation==result.saved.seller.reservation,'supplied role binders retain each policy own reservation separately'

    ceiling_checkpoint=replace(short.saved,state=replace(short.saved.state,closed=None))
    at_ceiling=run_bargain(ceiling_checkpoint,1)
    assert at_ceiling.status=='exhausted' and at_ceiling.new_offers==() and at_ceiling.saved.state.round==1 and at_ceiling.saved.offers==ceiling_checkpoint.offers,'an open checkpoint already at its total round ceiling emits no further offers'
    decimal_policy=PolicyInput(Decimal('0'),True,Decimal('100'),Decimal('100'),Decimal('1'),Decimal('0.29'))
    assert next_buyer_offer(decimal_policy)==Decimal('29'),'finite decimal concessions retain their exact directed tick movement'

@pytest.mark.skip('Part 4')
def test_actual_numeric_offer_and_matching_narrative_ndjson(tmp_path):
    """Project each actual public phase, numeric quote and exact narrative revision using supplied classification, revision lookup and async NDJSON lifecycle."""
    result=archived_run(tmp_path,'stream');events=public_events(result);catalog=NarrationCatalog(result.saved.offers)
    class Source:
        def __init__(self,items):self.items=iter(items);self.closed=False
        def __aiter__(self):return self
        async def __anext__(self):
            try:return next(self.items)
            except StopIteration:raise StopAsyncIteration
        async def aclose(self):self.closed=True
    async def collect(items,lookup):
        source=Source(items);frames=[frame async for frame in publish_events(source,lookup,event_fields)];return source,[json.loads(frame)for frame in frames]
    source,rows=asyncio.run(collect(events+(events[0],),catalog))
    assert source.closed and len(rows)==len(events) and rows[-1]['kind']=='accept','the supplied publication driver closes input and suppresses offers after a terminal event'
    first=result.new_offers[0];last=events[-1]
    assert rows[0]=={'negotiation_id':'stream','round':first.quote.round,'side':'seller','kind':'offer','price':str(first.quote.price),'offer_uid':first.quote.uid,'revision':first.quote.revision,'price_ticks':int(first.quote.price),'narration':first.narration.text},'each emitted row retains its actual phase numeric offer and own narrative evidence'
    assert rows[-1]['offer_uid']==result.saved.state.settlement.standing_uid and rows[-1]['price']=='50' and rows[-1]['revision']==last.quote.revision and rows[-1]['narration']==catalog.get(last.quote.uid,last.quote.revision).text,'acceptance projects the referenced standing quote and its matching narrative revision'
    q=Quote('revised','other','cpu',1,2,'buyer',Decimal('0.00'),Decimal('0.01'));q2=replace(q,revision=2,price=Decimal('1.25'));p1=PublicOffer(q,Narration(q.uid,1,'说明 999，仅文本'),0);p2=PublicOffer(q2,Narration(q2.uid,2,'修订\n报价'),125);lookup=NarrationCatalog((p1,p2))
    sample=(PublicEvent('other',2,'buyer','offer',q,1),PublicEvent('other',3,'buyer','offer',q2,2),PublicEvent('other',3,'seller','no-deal',None,None));_,observed=asyncio.run(collect(sample,lookup))
    assert observed[0]['price']=='0.00' and observed[0]['price_ticks']==0 and observed[0]['narration']=='说明 999，仅文本' and observed[1]['price']=='1.25' and observed[1]['price_ticks']==125 and observed[1]['narration']=='修订\n报价','numeric evidence and each exact revision remain independent of descriptive text and older revisions'
    assert observed[2]=={'negotiation_id':'other','round':3,'side':'seller','kind':'no-deal','price':None,'offer_uid':None,'revision':None,'price_ticks':None,'narration':None},'a no-deal phase retains its actual identity without inventing a numeric accepted offer'

    assert rows[-1]['round']==result.saved.state.round and observed[1]['round']==3,'public event rounds remain current when their standing quote was made earlier'

@pytest.mark.skip('Part 5')
def test_nested_quantity_coverage_and_all_party_joint_utility(tmp_path):
    """Build every private group report from own and child terms, complete issue coverage and joint per-party utility using actual earlier clearing evidence."""
    result=archived_run(tmp_path,'tree');price=result.saved.state.settlement.price
    parties=(PartyUtility('buyer',(UtilityRule('cpu',Decimal('40'),Decimal('-1')),UtilityRule('disk',Decimal('10'),Decimal('-1')),UtilityRule('delivery',Decimal('0'),Decimal('0')))),PartyUtility('seller',(UtilityRule('cpu',Decimal('-10'),Decimal('1')),UtilityRule('disk',Decimal('-1'),Decimal('1')),UtilityRule('delivery',Decimal('0'),Decimal('0')))))
    cpu=OfferTerm('cpu-term','cpu',Decimal('2'),price,Decimal('1'),Decimal('2'));disk=OfferTerm('disk-term','disk',Decimal('1'),Decimal('0'),Decimal('1'),Decimal('1'))
    left=OfferGroup('left',('cpu',),(('buyer',Decimal('20')),('seller',Decimal('20'))),(cpu,));right=OfferGroup('right',('disk',),(('buyer',Decimal('0')),('seller',Decimal('-2'))),(disk,));root=OfferGroup('root',('cpu','disk'),(('buyer',Decimal('30')),('seller',Decimal('20'))),children=('left','right'))
    def audit(groups):
        catalog=OfferCatalog(('cpu','disk','delivery'),parties,groups);return audit_offer_tree(catalog.expand('root'),catalog)
    actual=audit((left,right,root))
    assert actual.feasible and actual.terms==(cpu,disk) and actual.utilities==( ('buyer',Decimal('40')),('seller',Decimal('29'))) and actual.minimum_utilities==root.minimum_utilities,'nested joint feasibility consumes the actual reopened mechanism clearing price across all issue contributions'
    assert tuple(child.path for child in actual.children)==(('root','left'),('root','right')) and all(child.feasible for child in actual.children) and actual.first_blocker is None,'every declared nested layer retains its own private report and full term order'
    joint=audit((left,right,replace(root,minimum_utilities=(('buyer',Decimal('41')),('seller',Decimal('20'))))))
    assert not joint.feasible and all(child.feasible for child in joint.children) and joint.first_blocker.path==('root',) and joint.first_blocker.party_uid=='buyer','individually feasible children do not replace the parent joint private acceptance threshold'
    seller_joint=audit((left,right,replace(root,minimum_utilities=(('buyer',Decimal('30')),('seller',Decimal('30'))))))
    assert not seller_joint.feasible and seller_joint.first_blocker.party_uid=='seller','every declared party private minimum remains necessary for a joint agreement'
    assert public_blocker(joint)=={'path':['root'],'term_uid':None,'category':'joint-utility'},'the supplied public diagnostic exposes structural blocking evidence without private utility or threshold fields'
    bad=audit((replace(left,terms=(replace(cpu,quantity=Decimal('3')),)),right,root));missing=audit((left,right,replace(root,required_issues=('cpu','disk','delivery'))))
    assert bad.first_blocker.path==('root','left') and bad.first_blocker.term_uid=='cpu-term' and bad.first_blocker.category=='quantity' and bad.utilities==( ('buyer',Decimal('80')),('seller',Decimal('19'))),'a declared quantity violation retains its first exact nested witness and complete actual utility accounting'
    assert not missing.feasible and missing.first_blocker.path==('root',) and missing.first_blocker.term_uid=='delivery' and missing.first_blocker.category=='missing-issue','complete issue coverage remains required even when all existing terms are feasible'
    own_bad=OfferTerm('own-delivery','delivery',Decimal('2'),Decimal('0'),Decimal('0'),Decimal('1'))
    combined=audit((replace(left,terms=(replace(cpu,quantity=Decimal('3')),)),right,replace(root,terms=(own_bad,))))
    assert not combined.feasible and combined.first_blocker.path==('root',) and combined.first_blocker.term_uid=='own-delivery' and combined.first_blocker.category=='quantity' and combined.terms[0]==own_bad and not combined.children[0].feasible and combined.children[0].first_blocker.term_uid=='cpu-term' and combined.utilities==bad.utilities,'an own quantity witness precedes child blockers while all nested accounting remains complete'
