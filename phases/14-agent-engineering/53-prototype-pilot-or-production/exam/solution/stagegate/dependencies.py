"""Necessary responsibility edges, not a universal ordering of learning stages."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class Component:
    id:str
    owner:str
    controls:tuple[str,...]
    authority:tuple[str,...]
@dataclass(frozen=True)
class Dependency:
    parent:str
    child:str
    controls:tuple[str,...]=()
    owner_required:bool=True
    allowed_authority:tuple[str,...]=('read',)
    optional:bool=False
@dataclass(frozen=True)
class Deficit:
    component:str
    kind:str
    value:str
    path:tuple[str,...]

def required_paths(root:str,components:list[Component],edges:list[Dependency])->dict[str,tuple[str,...]]:
    """Correct supplied finite-DAG helper. All ids known/unique, edges acyclic.
    Paths use only necessary edges; return lexicographically smallest root-to-node
    path. Optional edges and subtrees reachable only through them impose no policy.
    Every edge is still independently auditable when a shared child has several
    requirements. This helper does not assign stages or inspect ownership/controls.
    """
    by_id={c.id:c for c in components}
    if len(by_id)!=len(components) or root not in by_id:raise ValueError('component identity')
    graph={n:[] for n in by_id}
    for edge in edges:
        if edge.parent not in by_id or edge.child not in by_id:raise ValueError('unknown component')
        if not edge.optional:graph[edge.parent].append(edge.child)
    degree={node:0 for node in graph}
    for children in graph.values():
        for child in children:degree[child]+=1
    ready=[node for node in graph if degree[node]==0];processed=0
    while ready:
        node=ready.pop();processed+=1
        for child in graph[node]:
            degree[child]-=1
            if degree[child]==0:ready.append(child)
    if processed!=len(graph):raise ValueError('dependency cycle')
    paths={root:(root,)};pending=[root]
    while pending:
        parent=pending.pop()
        for child in graph[parent]:
            path=paths[parent]+(child,)
            if child not in paths or path<paths[child]:paths[child]=path;pending.append(child)
    return paths

def responsibility_gaps(root:str,components:list[Component],edges:list[Dependency])->list[Deficit]:
    """This organization's explicit necessary-dependency policy: root needs an owner;
    each reachable necessary edge independently requires its child's owner if flagged,
    every named control, and no child authority outside that edge's allowed set. Stage
    labels are irrelevant: an isolated optional prototype may be legal. Controls and
    authority are explicit observed facts, not receipt kinds/claims. For each distinct
    (component,kind,value) deficit retain the smallest actual witness edge-path
    required_paths[parent]+(child,). Sort results by (component,kind,value). kind is
    owner/value='', control/value=missing name, or authority/value=excess permission.
    Skip optional and unreachable edges; shared children must satisfy every incoming
    necessary edge's independent demands. Use supplied path helper; no mutation.
    """
    paths=required_paths(root,components,edges);by_id={c.id:c for c in components};found={}
    def add(component,kind,value,path):
        key=(component,kind,value)
        if key not in found or path<found[key]:found[key]=path
    if not by_id[root].owner.strip():add(root,'owner','',(root,))
    for edge in edges:
        if edge.optional or edge.parent not in paths:continue
        child=by_id[edge.child];path=paths[edge.parent]+(edge.child,)
        if edge.owner_required and not child.owner.strip():add(child.id,'owner','',path)
        for control in edge.controls:
            if control not in child.controls:add(child.id,'control',control,path)
        for permission in child.authority:
            if permission not in edge.allowed_authority:add(child.id,'authority',permission,path)
    return [Deficit(*key,found[key]) for key in sorted(found)]
