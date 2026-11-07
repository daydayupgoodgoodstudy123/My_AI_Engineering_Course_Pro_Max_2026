"""Complete capability intake, separate channel routing, JSONL framing and exact metadata codec."""
from pathlib import Path
import json
from .models import Entry,SourceKey,VerificationFinding
from .support import ReadOnlyPool,FindingView
def encode_metadata(entry):
    return {'timestamp_ns':str(entry.timestamp_ns),'prompt_hash':entry.prompt_hash,'source':None if entry.source is None else {'uri':entry.source.uri,'version':entry.source.version},'supersedes':entry.supersedes}
def decode_metadata(meta):
    source=meta['source']
    return {'timestamp_ns':int(meta['timestamp_ns']),'prompt_hash':meta['prompt_hash'],'source':None if source is None else SourceKey(source['uri'],source['version']),'supersedes':meta['supersedes']}
def finding_document(finding):
    return {'entry_id':finding.entry_id,'source':{'uri':finding.source.uri,'version':finding.source.version},'verdict':finding.verdict,'detail':finding.detail}
def finding_value(document):
    return VerificationFinding(document['entry_id'],SourceKey(**document['source']),document['verdict'],document['detail'])
class LedgerDriver:
    """Only declared read capabilities may select their complete separate log channels."""
    def __init__(self,path):self.path=Path(path)
    def append(self,pool_view,finding_view,encode_entries):
        if type(pool_view)is not ReadOnlyPool or type(finding_view)is not FindingView:raise TypeError('declared read capabilities required')
        self.path.mkdir(parents=True,exist_ok=True)
        entries=pool_view.read_all();findings=finding_view.read_all()
        documents=encode_entries(entries)
        for filename,records in (('pool.jsonl',documents),('findings.jsonl',tuple(finding_document(f)for f in findings))):
            path=self.path/filename
            previous=tuple(json.loads(line)for line in path.read_text(encoding='utf-8').splitlines()) if path.exists()else ()
            if tuple(records[:len(previous)])!=previous:raise ValueError('append-only snapshot prefix required')
            with (self.path/filename).open('a',encoding='utf-8') as handle:
                for document in records[len(previous):]:handle.write(json.dumps(document,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
                handle.flush()
    def reopen(self,decode_entries):
        def read(name):
            path=self.path/name
            if not path.exists():return ()
            return tuple(json.loads(line)for line in path.read_text(encoding='utf-8').splitlines())
        return decode_entries(read('pool.jsonl')),tuple(finding_value(d)for d in read('findings.jsonl'))
