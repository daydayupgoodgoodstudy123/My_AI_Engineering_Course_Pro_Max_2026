"""GIVEN exact local finite-JSON codec. Tags distinguish every Python JSON value type."""
import json,math

def pack(value):
    if value is None:return ['null']
    if type(value) is bool:return ['bool',value]
    if type(value) is int:return ['int',str(value)]
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('finite local JSON')
        return ['float',value.hex()]
    if isinstance(value,str):return ['str',value]
    if isinstance(value,list):return ['list',[pack(item) for item in value]]
    if isinstance(value,dict) and all(isinstance(key,str) for key in value):return ['dict',[[key,pack(item)] for key,item in value.items()]]
    raise ValueError('finite local JSON')

def unpack(node):
    tag=node[0]
    if tag=='null':return None
    if tag=='bool':return node[1]
    if tag=='int':return int(node[1])
    if tag=='float':return float.fromhex(node[1])
    if tag=='str':return node[1]
    if tag=='list':return [unpack(item) for item in node[1]]
    if tag=='dict':return {key:unpack(item) for key,item in node[1]}
    raise ValueError('local value tag')

def encode(value):return json.dumps(pack(value),ensure_ascii=False,separators=(',',':')).encode('utf-8')
def decode(value):return unpack(json.loads(value.decode('utf-8')))

def same_value(left,right):
    """GIVEN typed finite-JSON equality; object key order is immaterial."""
    if type(left) is not type(right):return False
    if type(left) is float:return left.hex()==right.hex()
    if isinstance(left,list):return len(left)==len(right) and all(same_value(a,b) for a,b in zip(left,right))
    if isinstance(left,dict):return left.keys()==right.keys() and all(same_value(left[key],right[key]) for key in left)
    return left==right
