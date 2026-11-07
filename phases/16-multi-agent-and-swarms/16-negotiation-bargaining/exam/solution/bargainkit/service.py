"""Complete supplied-offer business facade; concession generators and bounded runner are separate TODOs."""
from .models import ReviewReceipt,BatchReview
from .support import validate_request,settlement_receipt
from .exact import amount_atoms
from . import primitives
class OfferDesk:
    def evaluate_supplied(self,request):
        validate_request(request)
        settlement=primitives.try_settlement(request.incoming,request.standing,request.buyer.reservation,request.seller.reservation)
        buyer,seller=settlement_receipt(request,settlement)
        own=request.buyer if request.incoming.side=='buyer'else request.seller
        public=primitives.public_offer_view(request.incoming,own)
        ticks=None if settlement is None else primitives.count_price_ticks(*amount_atoms(settlement.price,request.incoming.tick))
        return ReviewReceipt(request,settlement,buyer,seller,ticks,public)
    def review_many(self,requests):
        requests=tuple(requests);receipts=tuple(self.evaluate_supplied(request)for request in requests)
        return BatchReview(requests,receipts,sum(r.settlement is not None for r in receipts))
