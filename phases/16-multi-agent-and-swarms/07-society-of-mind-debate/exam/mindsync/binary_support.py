"""GIVEN complete binary64/scalar/text framing primitives and local file lifecycle."""
import struct
MAGIC=b'MSYNC\x01'
class BinaryWriter:
    def __init__(self,path):self.path=path
    def __enter__(self):self.file=open(self.path,'wb');self.file.write(MAGIC);return self
    def __exit__(self,*args):self.file.close()
    def count(self,n):self.file.write(struct.pack('>I',n))
    def index(self,n):self.file.write(struct.pack('>Q',n))
    def scalar(self,value):self.file.write(struct.pack('>d',value))
    def text(self,value):
        raw=value.encode('utf-8');self.count(len(raw));self.file.write(raw)
    def optional_scalar(self,value):
        self.file.write(b'\x00' if value is None else b'\x01')
        if value is not None:self.scalar(value)
class BinaryReader:
    def __init__(self,path):self.path=path
    def take(self,n):
        raw=self.file.read(n)
        if len(raw)!=n:raise ValueError('incomplete debate record')
        return raw
    def __enter__(self):
        self.file=open(self.path,'rb')
        try:
            if self.take(len(MAGIC))!=MAGIC:raise ValueError('invalid debate signature')
        except Exception:
            self.file.close();raise
        return self
    def __exit__(self,*args):self.file.close()
    def count(self):return struct.unpack('>I',self.take(4))[0]
    def index(self):return struct.unpack('>Q',self.take(8))[0]
    def scalar(self):return struct.unpack('>d',self.take(8))[0]
    def text(self):return self.take(self.count()).decode('utf-8')
    def optional_scalar(self):
        flag=self.take(1)
        if flag==b'\x00':return None
        if flag!=b'\x01':raise ValueError('invalid truth presence')
        return self.scalar()
    def ensure_end(self):
        if self.file.read(1):raise ValueError('extra debate bytes')
