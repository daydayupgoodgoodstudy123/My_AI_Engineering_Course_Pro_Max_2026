"""Complete exact tagged scalar/key codecs and typed unknown/target answer constructors."""
import json
from decimal import Decimal
from .models import BeliefKey,Prediction
def encode(value):
    if isinstance(value,tuple):return {'tuple':[encode(x)for x in value]}
    if isinstance(value,Decimal):return {'decimal':str(value)}
    if value is None or type(value)in(str,int,bool):return value
    raise TypeError('declared exact scalar tree required')
def decode(value):
    if isinstance(value,dict):
        if set(value)=={'tuple'}:return tuple(decode(x)for x in value['tuple'])
        if set(value)=={'decimal'}:return Decimal(value['decimal'])
        raise ValueError('tagged scalar required')
    return value
def dump_value(value):return json.dumps(encode(value),ensure_ascii=False)
def load_value(value):return decode(json.loads(value))
def dump_key(key):return dump_value((key.observer,key.subject,key.proposition))
def load_key(value):return BeliefKey(*load_value(value))
def prediction(model,target):return Prediction(model.subject,target,model.source_ids)
