"""Separately keyed durable definitions; injected policy callables are never serialized."""
from .agent import Agent
from .models import AgentDefinition,RunConfig,validate_definitions
from .config_support import ConfigDatabase

class PrimitiveConfiguration:
    def __init__(self,path):self.database=ConfigDatabase(path)
    def close(self):self.database.close()

    def save(self,definitions,config):
        """Store ordered immutable definitions and the run configuration as separate records."""
        raise NotImplementedError

    def load(self,registry):
        """Restore exact metadata and bind each named policy from the supplied registry."""
        raise NotImplementedError
