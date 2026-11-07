"""Complete typed intake and actual invitation delivery, without ranking or reflection solvers."""
from dataclasses import replace
from .models import Memory,MemoryFeature,AgentInspection
def validate_request(request):
    agents=request.population;ids=[a.uid for a in agents]
    if not agents or len(set(ids))!=len(ids)or request.sender_uid not in ids:raise ValueError('unique declared population and sender required')
    if request.window<0 or request.threshold<0:raise ValueError('nonnegative time window and threshold required')
    all_ids=[]
    for a in agents:
        if any(m.kind not in('observation','reflection')or not 1<=m.importance<=10 for m in a.memories):raise ValueError('typed memory required')
        all_ids.extend(m.uid for m in a.memories)
        if any(s.start>=s.end or s.revision<0 or s.status not in('active','cancelled')for s in a.plans):raise ValueError('finite positive plan intervals required')
    if len(set(all_ids))!=len(all_ids):raise ValueError('globally unique memory identities required')
    if any(invitation_uid(a.uid,request.now)in all_ids for a in agents if a.uid!=request.sender_uid):raise ValueError('fresh invitation identity required')
def invitation_uid(agent_uid,now):return 'invite:'+agent_uid+':'+str(now)
def observe_agent(population,index,request):
    recipient=population[index]
    seq=max((m.seq for m in recipient.memories),default=-1)+1
    memory=Memory(invitation_uid(recipient.uid,request.now),seq,request.now,'observation',request.invitation,8)
    return replace(recipient,memories=recipient.memories+(memory,))
def deliver_invitation(population,positions,request):
    result=list(population);delivered=[]
    for index in positions:
        updated=observe_agent(population,index,request);result[index]=updated;delivered.append(updated.uid)
    return tuple(result),tuple(delivered)
def inspect_agent(agent,request,feature,primitives):
    features=tuple(MemoryFeature(m,feature(m.content))for m in agent.memories if primitives.eligible_observation(m,request.now,request.window))
    pending=primitives.pending_importance_since(agent.memories,agent.progress,request.now,request.window)
    return AgentInspection(agent,features,pending,pending>=request.threshold)
def validate_proposal(state,proposal):
    if len(set(proposal.source_ids))!=len(proposal.source_ids):raise ValueError('unique proposal citations required')
    if any(m.uid==proposal.uid for m in state.memories)or any(b.uid==proposal.uid for b in state.beliefs):raise ValueError('fresh reflection identity required')
def validate_patches(patches):
    if len({p.segment_uid for p in patches})!=len(patches):raise ValueError('unique patch targets required')
    if any(p.start>=p.end or p.status not in('active','cancelled')for p in patches):raise ValueError('valid patch intervals required')
