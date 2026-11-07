"""GIVEN content addressing, exact UTF8 bytes, finite JSON and local I/O."""
from pathlib import Path
import hashlib,json

class ContentFiles:
    def __init__(self,root):
        self.root=Path(root);(self.root/'objects').mkdir(parents=True,exist_ok=True)
    def put_summary(self,text):
        data=text.encode('utf-8');digest=hashlib.sha256(data).hexdigest()
        (self.root/'objects'/digest).write_bytes(data)
        return digest
    def get_summary(self,digest):
        data=(self.root/'objects'/digest).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('artifact digest mismatch')
        return data.decode('utf-8')
    def write_manifest(self,query_id,row):
        key=hashlib.sha256(query_id.encode('utf-8')).hexdigest()
        (self.root/(key+'.json')).write_text(json.dumps(row,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    def read_manifest(self,query_id):
        key=hashlib.sha256(query_id.encode('utf-8')).hexdigest()
        return json.loads((self.root/(key+'.json')).read_text(encoding='utf-8'))
