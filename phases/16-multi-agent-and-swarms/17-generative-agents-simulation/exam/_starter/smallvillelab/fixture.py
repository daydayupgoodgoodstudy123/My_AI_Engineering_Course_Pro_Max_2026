"""Genuine query/memory inspection requests with complete independent expectations outside timing."""
from dataclasses import replace
from .models import Memory,Progress,AgentState,InspectionRequest,MemoryFeature,AgentInspection,Inspection
def inspection_fixture(count=5000,terms=4000):
    memories=tuple(Memory('m'+str(i),i,10,'observation','cafe memory '+str(i),1+i%10)for i in range(count))
    first=AgentState('sender','Sender','home',memories,Progress(tuple('m'+str(i)for i in range(0,count,7)),7))
    second=AgentState('recipient','Recipient','park')
    query='cafe '+' '.join('topic'+str(i)for i in range(terms));request=InspectionRequest((first,second),'sender','cafe invitation',10,5,query,25)
    observed=Memory('invite:recipient:10',0,10,'observation','cafe invitation',8);recipient=replace(second,memories=(observed,))
    pending=sum(1+i%10 for i in range(count)if i%7!=0)
    expected=Inspection(request,('recipient',),(AgentInspection(first,tuple(MemoryFeature(m,0.6)for m in memories),pending,pending>=25),AgentInspection(recipient,(MemoryFeature(observed,0.6),),8,False)))
    return request,expected
