"""Given tagged JSON values preserve exact finite binary64/int and typed empty data."""
import math
def pack_value(value):
    if value is None:return ["none"]
    if type(value) is bool:return ["bool",value]
    if type(value) is int:return ["int",str(value)]
    if type(value) is float:
        if not math.isfinite(value):raise ValueError("finite payload required")
        return ["float",value.hex()]
    if type(value) is str:return ["str",value]
    if type(value) is list:return ["list",[pack_value(item) for item in value]]
    if type(value) is dict and all(type(key) is str for key in value):return ["dict",[[key,pack_value(item)] for key,item in value.items()]]
    raise ValueError("local JSON payload required")
def unpack_value(value):
    tag=value[0]
    if tag=="none":return None
    if tag=="bool":return value[1]
    if tag=="int":return int(value[1])
    if tag=="float":
        result=float.fromhex(value[1])
        if not math.isfinite(result):raise ValueError("finite payload required")
        return result
    if tag=="str":return value[1]
    if tag=="list":return [unpack_value(item) for item in value[1]]
    if tag=="dict":return {key:unpack_value(item) for key,item in value[1]}
    raise ValueError("unknown local payload tag")
