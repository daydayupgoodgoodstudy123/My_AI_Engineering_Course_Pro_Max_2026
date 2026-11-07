from .models import IncidentRecord,Observation
from .csv_support import CSVRows
class IncidentArchive:
    def __init__(self,path):self.rows=CSVRows(path)
    def append(self,r):
        o=r.validation
        self.rows.append((r.uid,r.root,r.primary,r.symptoms,r.category,r.tags,r.action,r.call_budget,o.action_uid,o.at,o.cleared,o.note))
    def reopen_records(self):
        return tuple(IncidentRecord(*v[:8],Observation(*v[8:]))for v in self.rows.all())
    def close(self):self.rows.close()
