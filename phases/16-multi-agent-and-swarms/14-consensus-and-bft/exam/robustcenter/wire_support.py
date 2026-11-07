"""Complete explicit tags, actual probe binding, exact primitives, framing and async lifecycle."""
import json,struct
from .models import Ballot
from .support import ballot_intake
def public_observation(ballot):
    ballot_intake((ballot,),1)
    from .primitives import canonicalize_proposal
    key=canonicalize_proposal(ballot.proposal.answer)if ballot.proposal.kind=='ANSWER'else None
    return {'kind':ballot.proposal.kind,'proposal':ballot.proposal,'probe':ballot.probe,'numeric':key}
def fraction_pair(value):return [str(value.numerator),str(value.denominator)]
def numeric_fields(observation):
    key=observation['numeric']
    return (None,None)if key is None else (str(key.value),key.unit)
def probe_payload(observation):
    q=observation['probe']
    return {'probe_uid':q.probe_uid,'probe_confidence':fraction_pair(q.confidence),'evaluator':q.evaluator,'assessment':q.assessment}
def frame(payload):
    body=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    return struct.pack('!I',len(body))+body
async def publish_frames(source,project):
    try:
        async for ballot in source:yield frame(project(public_observation(ballot)))
    finally:
        close=getattr(source,'aclose',None)
        if close is not None:await close()
