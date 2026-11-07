"""Separately keyed durable definitions; injected policy callables are never serialized."""
from .agent import Agent
from .models import AgentDefinition,RunConfig,validate_definitions
from .config_support import ConfigDatabase

class PrimitiveConfiguration:
    def __init__(self,path):self.database=ConfigDatabase(path)
    def close(self):self.database.close()

    def save(self,definitions,config):
        """Store ordered immutable definitions and the run configuration as separate records."""
        validate_definitions(definitions,config)
        for item in definitions:
            self.database.put('agent',item.name,{'version':1,'name':item.name,'system_prompt':item.system_prompt,'tools':list(item.tools),'policy_name':item.policy_name})
        self.database.put('run','config',{'version':1,'agent_names':[item.name for item in definitions],'mode':config.mode,'order':list(config.order),'start':config.start,'max_steps':config.max_steps})

    def load(self,registry):
        """Restore exact metadata and bind each named policy from the supplied registry."""
        row=self.database.get('run','config')
        if type(row['version']) is not int or row['version']!=1:raise ValueError('unsupported primitive configuration version')
        definitions=[];team={}
        for name in row['agent_names']:
            item=self.database.get('agent',name)
            if type(item['version']) is not int or item['version']!=1:raise ValueError('unsupported primitive configuration version')
            policy_name=item['policy_name']
            if policy_name not in registry:raise ValueError('unknown local policy')
            definition=AgentDefinition(item['name'],item['system_prompt'],tuple(item['tools']),policy_name)
            definitions.append(definition)
            team[definition.name]=Agent(definition.name,definition.system_prompt,definition.tools,registry[policy_name])
        config=RunConfig(row['mode'],tuple(row['order']),row['start'],row['max_steps'])
        validate_definitions(definitions,config)
        return definitions,config,team
