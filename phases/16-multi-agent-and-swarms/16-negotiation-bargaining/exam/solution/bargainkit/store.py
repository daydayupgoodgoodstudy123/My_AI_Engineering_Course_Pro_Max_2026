"""Model complete buyer/seller continuation and round state; scalar codecs and public/private channels are supplied."""
from .models import BargainState,SavedBargain
from .journal_support import DualJournal,strategy_fields,strategy_value,quote_fields,quote_value,settlement_fields,settlement_value
from .exact import price_field,price_value
class BargainArchive:
    def __init__(self,directory):self._driver=DualJournal(directory)
    def save(self,saved):
        """Append this checkpoint's complete private continuation and linked ordered public offers to supplied separate channels."""
        s=saved.state
        document={'negotiation_id':s.negotiation_id,'issue_id':s.issue_id,'tick':price_field(s.tick),'round':s.round,'revision':s.revision,'next_side':s.next_side,'buyer_quote':quote_fields(s.buyer_quote),'seller_quote':quote_fields(s.seller_quote),'closed':s.closed,'settlement':settlement_fields(s.settlement),'buyer':strategy_fields(saved.buyer),'seller':strategy_fields(saved.seller)}
        self._driver.save(saved.checkpoint_uid,document,saved.offers)
    def load(self,uid):
        """Reopen the exact own checkpoint, separate standing sides, private strategies and ordered public continuation."""
        d=self._driver.load_private(uid)
        state=BargainState(d['negotiation_id'],d['issue_id'],price_value(d['tick']),d['round'],d['revision'],d['next_side'],quote_value(d['buyer_quote']),quote_value(d['seller_quote']),d['closed'],settlement_value(d['settlement']))
        return SavedBargain(uid,state,strategy_value(d['buyer']),strategy_value(d['seller']),self._driver.load_public(uid))
    def public_history(self,uid):return self._driver.load_public(uid)
    def close(self):self._driver.close()
