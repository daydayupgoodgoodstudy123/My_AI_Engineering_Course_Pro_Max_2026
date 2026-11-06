"""Binary64 local adapter archive with explicit shape and module identity."""
import struct
from .envelope import wrap_archive,read_archive
from .models import Adapter,valid_adapter
def encode_adapter(adapter):
    """Return exact binary64 A/B/alpha and UTF8 module metadata in a complete local archive."""
    adapter=valid_adapter(adapter)
    ni,nr,no=len(adapter.A),adapter.rank,len(adapter.B[0])
    meta={"path":adapter.path,"input":ni,"rank":nr,"output":no}
    values=[adapter.alpha]+[x for row in adapter.A for x in row]+[x for row in adapter.B for x in row]
    payload=struct.pack(">"+"d"*len(values),*values)
    return wrap_archive(meta,payload)
def decode_adapter(raw):
    """Read exactly one complete archive, rejecting inconsistent or trailing bytes."""
    meta,payload=read_archive(raw);np=len(payload)
    ni,nr,no=(meta[k] for k in ("input","rank","output"))
    if any(type(n) is not int or n<=0 for n in (ni,nr,no)) or np!=8*(1+ni*nr+nr*no):raise ValueError("adapter payload shape disagrees")
    values=struct.unpack(">"+"d"*(np//8),payload)
    alpha=values[0];cut=1+ni*nr
    A=tuple(tuple(values[1+i*nr:1+(i+1)*nr]) for i in range(ni))
    B=tuple(tuple(values[cut+i*no:cut+(i+1)*no]) for i in range(nr))
    return valid_adapter(Adapter(meta["path"],A,B,alpha))
class AdapterArchive:
    def __init__(self,path):self.path=path
    def save(self,adapter):
        """Persist one complete validated adapter artifact."""
        self.path.write_bytes(encode_adapter(adapter))
    def load(self):
        """Reopen the same named adapter without numeric narrowing."""
        return decode_adapter(self.path.read_bytes())
