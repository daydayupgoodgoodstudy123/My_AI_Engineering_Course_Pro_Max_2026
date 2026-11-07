"""Policy-free execution capture. Handler emit callbacks record observed tool work."""
from copy import deepcopy
from .models import Observation

def capture_once(store,run_id,agent,inputs,handler,clock,session_id=None):
    """Execute one handler once; seal either result or failure into the same run."""
    store.begin(run_id,agent,inputs,session_id,clock())
    def emit(event):store.append(run_id,event)
    try:
        result=handler(inputs,emit)
        returned=handler(inputs,emit)
    except Exception as exc:
        result=None;returned=None
        error={'type':type(exc).__name__,'message':str(exc)}
    else:error=None
    store.seal(run_id,result,error,clock())
    return Observation(store.read(run_id),deepcopy(returned))
