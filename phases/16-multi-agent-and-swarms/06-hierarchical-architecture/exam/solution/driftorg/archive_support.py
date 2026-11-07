"""GIVEN complete typed domain codec, finite UTF8/JSON and ZIP I/O primitives."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib,json,zipfile
from .models import Leaf,Node,Status

def encode_json(value):return json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8')
def decode_json(value):return json.loads(value.decode('utf-8'))
def encode_leaf(leaf):
    row=asdict(leaf);row['status']=leaf.status.value;return encode_json(row)
def decode_leaf(data):
    r=decode_json(data)
    return Leaf(r['leaf_id'],r['worker'],r['obligation'],r['department'],r['question'],r['answer'],Status(r['status']),tuple(r['citation_ids']))
def encode_node(node):return encode_json(asdict(node))
def decode_node(data):
    r=decode_json(data)
    return Node(r['node_id'],r['department'],tuple(r['obligations']),tuple(r['children']),tuple(tuple(p) for p in r['bindings']),tuple(r['leaf_ids']),r['summary'],r['available'])
def member_name(kind,logical_id):return kind+'/'+hashlib.sha256(logical_id.encode('utf-8')).hexdigest()+'.json'

class Archive:
    def __init__(self,path,mode):self._zip=zipfile.ZipFile(path,mode,compression=zipfile.ZIP_STORED)
    def put(self,name,data):self._zip.writestr(name,data)
    def get(self,name):
        try:return self._zip.read(name)
        except KeyError as exc:raise ValueError('missing archive member') from exc
    def close(self):self._zip.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
