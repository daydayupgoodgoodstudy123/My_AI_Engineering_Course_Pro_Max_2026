"""GIVEN complete tagged model/value codec; no float narrowing or code execution."""
import dataclasses,json
from . import models
_TYPES={n:getattr(models,n) for n in dir(models) if isinstance(getattr(models,n),type) and dataclasses.is_dataclass(getattr(models,n))}
def to_value(value):
    if value is None:return ['none']
    if type(value) is bool:return ['bool',value]
    if type(value) is int:return ['int',str(value)]
    if type(value) is float:return ['float',value.hex()]
    if type(value) is str:return ['str',value]
    if dataclasses.is_dataclass(value):return ['model',type(value).__name__,[[f.name,to_value(getattr(value,f.name))] for f in dataclasses.fields(value)]]
    if type(value) in (tuple,list):return ['tuple' if type(value)is tuple else 'list',[to_value(v) for v in value]]
    if type(value) is dict:return ['dict',[[to_value(k),to_value(v)]for k,v in value.items()]]
    raise ValueError('unsupported local record value')
def from_value(value):
    tag=value[0]
    if tag=='none':return None
    if tag=='bool':return value[1]
    if tag=='int':return int(value[1])
    if tag=='float':return float.fromhex(value[1])
    if tag=='str':return value[1]
    if tag in ('list','tuple'):
        items=[from_value(v)for v in value[1]];return tuple(items) if tag=='tuple'else items
    if tag=='dict':return {from_value(k):from_value(v)for k,v in value[1]}
    if tag=='model':return _TYPES[value[1]](**{k:from_value(v)for k,v in value[2]})
    raise ValueError('unknown local record tag')
def encode(value):return json.dumps(to_value(value),ensure_ascii=False,separators=(',',':'))
def decode(value):return from_value(json.loads(value))
