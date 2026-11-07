"""Complete explicit-tag artifact codec and local directory I/O primitives."""
import json
from pathlib import Path
def encode_artifact(artifact):
    if artifact.type=='text':
        if not isinstance(artifact.data,str):raise ValueError('text data')
        return artifact.type,artifact.data.encode('utf-8')
    if artifact.type=='structured':return artifact.type,json.dumps(artifact.data,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    raise ValueError('known local artifact tag')
def decode_artifact(tag,payload):
    from .models import Artifact
    if tag=='text':return Artifact(tag,payload.decode('utf-8'))
    if tag=='structured':return Artifact(tag,json.loads(payload.decode('utf-8')))
    raise ValueError('known local artifact tag')
class DirectoryFiles:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
    def put(self,name,data):(self.path/name).write_bytes(data)
    def get(self,name):return(self.path/name).read_bytes()
    def write_manifest(self,entries):self.put('manifest.json',json.dumps(entries,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8'))
    def read_manifest(self):return json.loads(self.get('manifest.json').decode('utf-8'))
def member_name(index):return f'artifact-{index:06d}.bin'
