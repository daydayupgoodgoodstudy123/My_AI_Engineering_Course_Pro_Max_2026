"""Real numeric supplied offers and independent complete-review expectations outside timing."""
from decimal import Decimal
from fractions import Fraction
from .models import Strategy,Quote,Narration,PublicOffer,Settlement,SuppliedRequest,ReviewReceipt,BatchReview
def pair():return Strategy('buyer','buyer',Decimal('1500.00'),Decimal('800.00'),Fraction(1,2)),Strategy('seller','seller',Decimal('700.00'),Decimal('1200.00'),Fraction(1,2))
def review_fixture(count=128):
    buyer,seller=pair();requests=[];receipts=[]
    for i in range(count):
        negotiation='case-'+str(i);price=Decimal('1000.00')+Decimal(i).scaleb(-2)
        q=Quote('bid-'+str(i),negotiation,'item-'+str(i),i+1,0,'buyer',price,Decimal('0.01'))
        standing=Quote('ask-'+str(i),negotiation,'item-'+str(i),0,0,'seller',Decimal('900.00'),Decimal('0.01'))
        request=SuppliedRequest(q,standing,buyer,seller);requests.append(request)
        public=PublicOffer(q,Narration(q.uid,q.revision,'buyer offers '+str(price)+' USD'),100000+i)
        receipts.append(ReviewReceipt(request,Settlement(negotiation,q.issue_id,standing.uid,Decimal('900.00')),Decimal('600'),Decimal('200'),90000,public))
    return tuple(requests),BatchReview(tuple(requests),tuple(receipts),count)
