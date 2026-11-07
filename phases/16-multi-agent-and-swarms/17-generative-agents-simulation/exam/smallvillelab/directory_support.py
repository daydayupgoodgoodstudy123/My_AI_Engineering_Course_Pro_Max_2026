"""Complete normal-process UTF8 directory/member driver and exact scalar codec boundary."""
from pathlib import Path
import hashlib,json
from .scalar_codec import encode,decode
class DirectoryDriver:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True);self.closed=False
    def write(self,manifest,documents):
        if self.closed:raise ValueError('closed directory')
        members=[]
        for uid,document in documents:
            filename=hashlib.sha256(uid.encode('utf8')).hexdigest()+'.json';members.append((uid,filename))
            (self.path/filename).write_text(json.dumps(encode(document),ensure_ascii=False),encoding='utf8')
        (self.path/'manifest.json').write_text(json.dumps(encode({'manifest':manifest,'members':tuple(members)}),ensure_ascii=False),encoding='utf8')
    def read(self):
        if self.closed:raise ValueError('closed directory')
        data=decode(json.loads((self.path/'manifest.json').read_text(encoding='utf8')));documents={}
        for uid,filename in data['members']:
            if filename!=hashlib.sha256(uid.encode('utf8')).hexdigest()+'.json':raise ValueError('invalid member binding')
            documents[uid]=decode(json.loads((self.path/filename).read_text(encoding='utf8')))
        return data['manifest'],documents
    def close(self):self.closed=True
