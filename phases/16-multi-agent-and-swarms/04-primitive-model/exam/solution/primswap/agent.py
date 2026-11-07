"""Stateless agent metadata and canonical message producer identity."""
from copy import deepcopy
from dataclasses import dataclass

@dataclass(frozen=True)
class Agent:
    name: str
    system_prompt: str
    tools: tuple[str,...]
    policy: object

    def run(self,state):
        """Run the injected policy and own its result under this invoked agent's identity."""
        message=deepcopy(self.policy(state))
        message['from']=self.name
        return message
