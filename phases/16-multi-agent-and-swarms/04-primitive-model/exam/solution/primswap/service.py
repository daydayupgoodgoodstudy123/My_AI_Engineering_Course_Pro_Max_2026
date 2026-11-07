"""GIVEN single-step consumers and complete latest-draft review service."""
from copy import deepcopy
from .control import resolve_target

def evidence_consumer(messages,required_sender):
    by_sender={message['from']:message for message in messages}
    return deepcopy(by_sender[required_sender]['content'])

def completion_consumer(outcome):
    return {'kind':outcome.kind,'target':outcome.name,'successful_stop':outcome.kind in ('done','selector-stop')}

class SingleStepDesk:
    def execute(self,agent,state,required_sender):
        message=agent.run(state);state.append(message)
        return {'message':message,'evidence':evidence_consumer(state.snapshot(),required_sender)}

    def resolve_handoff(self,message,team):
        return completion_consumer(resolve_target(message.get('handoff','done'),team))

class ReviewDesk:
    def __init__(self,state):self.state=state

    def review(self,request):
        """Return the requested writer's actual latest draft and a local keyword verdict."""
        message=self.state.last_by(request['writer'])
        return {'request_id':request['request_id'],'writer':request['writer'],
            'draft':None if message is None else message['content'],
            'message_id':None if message is None else message['id'],
            'verdict':'missing' if message is None else ('approved' if 'summarizing' in message['content'] else 'needs revision')}
