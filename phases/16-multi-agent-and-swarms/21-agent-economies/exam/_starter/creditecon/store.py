"""Durable complete domain snapshots: own criterion, observation, permutation, quality and credit records."""
from .models import Game,Criterion,UtilityReceipt,ReplayReport,QualityReceipt,Efficiency,AccountingSnapshot
from .db_support import RowDriver
class AccountingArchive:
    def __init__(self,path):self.driver=RowDriver(path)
    def save(self,snapshot):
        """Replace the complete snapshot, preserving declared orders and separate surplus/total fields."""
        raise NotImplementedError('Complete the declared domain contract')
    def load(self):
        """Reopen every saved domain field, including repeated equal observations and unconfirmed receipts."""
        raise NotImplementedError('Complete the declared domain contract')
    def close(self):self.driver.close()
