"""GIVEN complete round/agent identities, prior-vector lookup and finite trace checks."""
class RoundCatalog:
    def __init__(self,records):
        self.records=tuple(records);self.by_index={r.index:r for r in self.records}
        if len(self.by_index)!=len(self.records) or tuple(self.by_index)!=tuple(range(len(self.records))):raise ValueError('contiguous round records required')
        if not self.records:raise ValueError('nonempty sealed trace required')
        self.names=tuple(a.name for a in self.records[0].agents)
        if any(tuple(a.name for a in r.agents)!=self.names for r in self.records):raise ValueError('aligned named round vectors required')
    def record(self,index):
        if index not in self.by_index:raise ValueError('unknown round')
        return self.by_index[index]
    def agent(self,index,name):
        record=self.record(index)
        for agent in record.agents:
            if agent.name==name:return agent
        raise ValueError('unknown round agent')
    def previous(self,index):return None if index==0 else self.record(index-1)
