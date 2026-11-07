"""Composite retrieval ranking, grounded reflection updates and local affected-plan revision."""
from dataclasses import replace
from math import exp
from .models import RankedMemory,Memory,Progress,Belief,ReflectionResult,RevisionResult,Segment
from .primitives import eligible_observation,pending_importance_since,prepare_query
from .support import validate_proposal,validate_patches
def rank_memories(state,now,window,query,k,decay=0.3):
    """Rank all available memories by recency plus importance plus supplied lexical relevance, preserving ties."""
    feature=prepare_query(query)
    scored=[RankedMemory(m.uid,exp(-decay*(now-m.tick))+m.importance/10+feature(m.content))for m in state.memories if eligible_observation(m,now,window)]
    return tuple(sorted(scored,key=lambda x:-x.score)[:k])
def reflect_from_sources(state,proposal,now,window,threshold):
    """At a due gate, cite actual eligible unconsumed raw observations and update only their independent progress."""
    validate_proposal(state,proposal);by_id={m.uid:m for m in state.memories};consumed=set(state.progress.consumed_source_ids)
    valid=tuple(uid for uid in proposal.source_ids if uid in by_id and by_id[uid].kind=='observation'and eligible_observation(by_id[uid],now,window)and uid not in consumed)
    rejected=tuple(uid for uid in proposal.source_ids if uid not in valid)
    if pending_importance_since(state.memories,state.progress,now,window)<threshold or not valid:return ReflectionResult(state,(),rejected,None)
    memory=Memory(proposal.uid,proposal.seq,now,'reflection',proposal.text,6,valid)
    belief=Belief(proposal.uid,proposal.text,valid)
    progress=Progress(state.progress.consumed_source_ids+valid,now)
    updated=replace(state,memories=state.memories+(memory,),beliefs=state.beliefs+(belief,),progress=progress)
    return ReflectionResult(updated,valid,rejected,proposal.uid)
def revise_affected_plan(reflection,patches):
    """Revise only current segments contradicted by the reflection's actual cited observations; retain unresolved targets."""
    validate_patches(patches);state=reflection.state;by_id={m.uid:m for m in state.memories};causes={}
    for uid in reflection.used_source_ids:
        for target in by_id[uid].contradicts:causes.setdefault(target,[]).append(uid)
    replacement={p.segment_uid:p for p in patches};affected=[];changed=[];unresolved=[];plans=[]
    for segment in state.plans:
        if segment.uid not in causes:plans.append(segment);continue
        affected.append(segment.uid)
        if segment.uid not in replacement:unresolved.append(segment.uid);plans.append(segment);continue
        p=replacement[segment.uid]
        plans.append(Segment(segment.uid,segment.revision+1,p.start,p.end,p.venue_uid,p.note,p.status,tuple(causes[segment.uid])));changed.append(segment.uid)
    return RevisionResult(replace(state,plans=tuple(plans)),tuple(affected),tuple(changed),tuple(unresolved))
