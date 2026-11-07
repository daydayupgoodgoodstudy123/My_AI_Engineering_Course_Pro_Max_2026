"""Complete pool snapshots, independent finding capabilities and topic callbacks."""
from dataclasses import dataclass
from hashlib import sha256
import re
from .models import Entry,VerificationFinding
@dataclass
class _MutableEntry:
    entry_id:int
    writer:str
    topic:str
    content:str
    timestamp_ns:int
    prompt_hash:str
    source:object=None
    supersedes:int|None=None
    def value(self):return Entry(self.entry_id,self.writer,self.topic,self.content,self.timestamp_ns,self.prompt_hash,self.source,self.supersedes)
class ReadOnlyPool:
    """Only immutable Entry snapshots are available through this handle."""
    def __init__(self,pool):self.__pool=pool
    def read_all(self):return tuple(e.value()for e in self.__pool._entries)
class MessagePool:
    """Append IDs are global within this pool and do not change when a version retires."""
    def __init__(self):self._entries=[]
    def append(self,writer,topic,content,timestamp_ns,prompt_hash,source=None,supersedes=None):
        entry=_MutableEntry(len(self._entries),writer,topic,content,timestamp_ns,prompt_hash,source,supersedes)
        self._entries.append(entry);return entry.entry_id
    def writer_record(self,entry_id):return self._entries[entry_id]
    def read_only(self):return ReadOnlyPool(self)
class FindingView:
    def __init__(self,channel):self.__channel=channel
    def read_all(self):return tuple(self.__channel._findings)
class VerificationChannel:
    """A separate typed capability; ordinary pool writer labels cannot create findings."""
    def __init__(self):self._findings=[]
    def emit(self,finding):
        if type(finding)is not VerificationFinding or finding.verdict not in ('MATCH','DISPUTE'):raise ValueError('typed independent finding required')
        self._findings.append(finding)
    def read_only(self):return FindingView(self)
class Blackboard:
    """Indexed topics with a callback snapshot for each publish; reentrant changes affect later publishes."""
    def __init__(self):self._callbacks={}
    def subscribe(self,topic,callback):self._callbacks.setdefault(topic,[]).append(callback)
    def unsubscribe(self,topic,callback):self._callbacks[topic].remove(callback)
    def publish(self,entry):
        for callback in tuple(self._callbacks.get(entry.topic,())):callback(entry)
def prompt_digest(prompt):return sha256(prompt.encode('utf-8')).hexdigest()
def require_percent_claim(text):
    """A percent-bearing summary requires a complete signed decimal number with its unit."""
    match=re.search(r'(?<![\w.])[+-]?\d+(?:\.\d+)?%',text)
    if match is None:raise ValueError('percentage claim with unit required')
    return match.group(0)
def source_matches(entry,snapshot):
    """Fixed-fixture exact comparison; this is not natural-language factual verification."""
    return VerificationFinding(entry.entry_id,snapshot.key,'MATCH' if entry.content==snapshot.text else 'DISPUTE','exact fixture comparison')
