"""Private in-memory audit ownership, independent of admission/public policy."""
from copy import deepcopy

class AuditStore:
    def __init__(self):self._runs={}

    def begin(self,run_id,agent,inputs,session_id,started_at):
        """Start a distinct run with an owned input snapshot and ordered observations."""
        if run_id in self._runs:raise ValueError('duplicate local run')
        self._runs[run_id]={'run_id':run_id,'agent':agent,'session_id':session_id,
            'input':deepcopy(inputs),'output':[],'trajectory':[],
            'status':'in-progress','started_at':started_at}

    def append(self,run_id,event):
        """Own this newly observed trajectory entry without exposing private state."""
        self._runs[run_id]['trajectory'].append(deepcopy(event))

    def seal(self,run_id,result,error,completed_at):
        """Seal success or failure, including the completion time and exact error evidence."""
        entry=self._runs[run_id]
        entry['status']='failed' if error is not None else 'completed'
        entry['completed_at']=completed_at
        entry['error']=deepcopy(error)
        entry['invocation_id']=None if result is None else result['invocation_id']
        entry['output']=[] if result is None else deepcopy(result['parts'])

    def read(self,run_id):
        """Return an independent snapshot of a run."""
        return deepcopy(self._runs[run_id])

    def all(self):
        """Return all owned run snapshots in creation order."""
        return deepcopy(list(self._runs.values()))
