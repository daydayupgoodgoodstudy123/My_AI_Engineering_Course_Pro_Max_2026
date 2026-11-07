from .models import IncidentRecord,Observation
from .csv_support import CSVRows
class IncidentArchive:
    def __init__(self,path):self.rows=CSVRows(path)
    def append(self,r):
        raise NotImplementedError('map full incident and independent observation to CSV')
    def reopen_records(self):
        raise NotImplementedError('reopen every original incident row in order')
    def close(self):self.rows.close()
