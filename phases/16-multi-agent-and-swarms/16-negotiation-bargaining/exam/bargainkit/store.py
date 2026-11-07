"""Model complete buyer/seller continuation and round state; scalar codecs and public/private channels are supplied."""
from .models import BargainState,SavedBargain
from .journal_support import DualJournal,strategy_fields,strategy_value,quote_fields,quote_value,settlement_fields,settlement_value
from .exact import price_field,price_value
class BargainArchive:
    def __init__(self,directory):self._driver=DualJournal(directory)
    def save(self,saved):
        """Append this checkpoint's complete private continuation and linked ordered public offers to supplied separate channels."""
        raise NotImplementedError
    def load(self,uid):
        """Reopen the exact own checkpoint, separate standing sides, private strategies and ordered public continuation."""
        raise NotImplementedError
    def public_history(self,uid):return self._driver.load_public(uid)
    def close(self):self._driver.close()
