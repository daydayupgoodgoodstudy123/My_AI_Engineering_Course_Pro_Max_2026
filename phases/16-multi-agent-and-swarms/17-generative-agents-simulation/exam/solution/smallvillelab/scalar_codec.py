"""Complete exact scalar/list/tuple JSON-value codec; no AgentState document schema."""
from decimal import Decimal
def encode(value):
    if isinstance(value,Decimal):return {'$decimal':str(value)}
    if isinstance(value,tuple):return {'$tuple':[encode(x)for x in value]}
    if isinstance(value,list):return [encode(x)for x in value]
    if isinstance(value,dict):return {k:encode(v)for k,v in value.items()}
    if value is None or type(value)in(str,int,bool):return value
    raise TypeError('declared exact scalar tree required')
def decode(value):
    if isinstance(value,dict):
        if set(value)=={'$decimal'}:return Decimal(value['$decimal'])
        if set(value)=={'$tuple'}:return tuple(decode(x)for x in value['$tuple'])
        return {k:decode(v)for k,v in value.items()}
    if isinstance(value,list):return [decode(x)for x in value]
    return value
