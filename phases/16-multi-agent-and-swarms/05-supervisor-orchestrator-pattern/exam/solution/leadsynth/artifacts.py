"""Durable assignment manifests over content-addressed summaries."""
from .models import Artifact,Claim
from .storage_support import ContentFiles

class ArtifactStore:
    def __init__(self,root):self.files=ContentFiles(root)
    def save(self,query_id,artifacts):
        """Persist exact summary objects plus ordered, query-specific assignments."""
        rows=[]
        for item in artifacts:
            rows.append({'question_id':item.question_id,'question':item.question,'scope':list(item.scope),'digest':self.files.put_summary(item.summary),'tokens':item.tokens,'seconds':item.seconds,'cut':item.cut,'claims':[{'claim_id':c.claim_id,'value':c.value,'source_ids':list(c.source_ids),'topic':c.topic} for c in item.claims]})
        self.files.write_manifest(query_id,{'query_id':query_id,'assignments':rows})
    def load(self,query_id):
        """Restore assignments in their declared order without merging shared content."""
        row=self.files.read_manifest(query_id)
        if row['query_id']!=query_id:raise ValueError('query identity mismatch')
        return [Artifact(r['question_id'],r['question'],tuple(r['scope']),self.files.get_summary(r['digest']),r['tokens'],r['seconds'],r['cut'],tuple(Claim(c['claim_id'],c['value'],tuple(c['source_ids']),c['topic']) for c in r['claims'])) for r in row['assignments']]
