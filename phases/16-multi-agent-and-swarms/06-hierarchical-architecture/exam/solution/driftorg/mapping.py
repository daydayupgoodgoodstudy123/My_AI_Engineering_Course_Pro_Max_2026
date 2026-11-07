"""Finite explicit obligation mappings, not inferred meaning from summary prose."""
from .models import Status
from .primitives import fold_descendant_ids

def compose_obligation_mappings(dossier):
    """Trace every original obligation through declared parent/child bindings.

    Record routes and leaf evidence. Missing managers, department mismatches,
    undeclared local obligation ids and unmapped obligations are separate issues.
    No structural leaf id alone can satisfy an original semantic obligation.
    """
    output={}
    for original,department in dossier.obligations:
        routes=[];issues=[];evidence=[];stack=[(dossier.root_id,original,())]
        while stack:
            ident,local,path=stack.pop();here=path+(ident,);node=dossier.nodes[ident]
            routes.append({'path':here,'local_obligation':local})
            if not node.available:issues.append({'path':here,'reason':'missing-branch'});continue
            if node.department is not None and node.department!=department:issues.append({'path':here,'reason':'wrong-branch'});continue
            if local not in node.obligations:issues.append({'path':here,'reason':'unsupported-mapping'});continue
            selected=[dossier.leaves[i] for i in node.leaf_ids if dossier.leaves[i].obligation==local]
            for leaf in selected:
                if leaf.department!=department:issues.append({'path':here+(leaf.leaf_id,),'reason':'wrong-branch'})
                else:evidence.append({'leaf_id':leaf.leaf_id,'path':here+(leaf.leaf_id,),'state':leaf.status.value})
            bindings=[binding for binding in node.bindings if binding[0]==local]
            if not selected and not bindings:issues.append({'path':here,'reason':'unmapped'})
            for parent,child,child_local in reversed(bindings):stack.append((child,child_local,here))
        output[original]={'routes':routes,'issues':issues,'evidence':evidence}
    return output

def first_divergence_path(composed):
    """Choose each obligation's earliest issue by path length, then encounter order."""
    return {ident:(min(row['issues'],key=lambda issue:len(issue['path'])) if row['issues'] else None) for ident,row in composed.items()}

def audit_decomposition(dossier,canary):
    """Audit explicit obligations and compare separately attributed canary evidence.

    Canary must name the unchanged original question; unsupported obligation ids
    are errors. Unknown leaf evidence remains unknown, not a negative answer.
    A known canary/hierarchy disagreement is labelled canary-mismatch while both
    states remain explicit. Structural provenance comes from repaired P1 only.
    """
    required={ident for ident,department in dossier.obligations}
    if canary['question']!=dossier.original_question:raise ValueError('canary question mismatch')
    if set(canary['states'])-required:raise ValueError('unsupported canary obligation')
    composed=compose_obligation_mappings(dossier);divergence=first_divergence_path(composed)
    rows=[]
    for ident,department in dossier.obligations:
        row=composed[ident];issue=divergence[ident];states=[item['state'] for item in row['evidence']]
        if issue is not None:hierarchy=issue['reason']
        elif not states:hierarchy='missing-evidence'
        elif 'unknown' in states:hierarchy='unknown'
        elif 'missing' in states:hierarchy='missing-evidence'
        elif len(set(states))>1:hierarchy='conflict'
        else:hierarchy=states[0]
        canary_state=canary['states'].get(ident)
        result='canary-mismatch' if hierarchy in ('verified','negative') and canary_state in ('verified','negative') and hierarchy!=canary_state else hierarchy
        rows.append({'obligation':ident,'department':department,'hierarchy_state':hierarchy,'canary_state':canary_state,'result':result,'first_divergence':issue,'evidence':row['evidence']})
    return {'rows':rows,'mappings':composed,'structural':fold_descendant_ids(dossier.nodes,dossier.leaves,dossier.root_id)}
