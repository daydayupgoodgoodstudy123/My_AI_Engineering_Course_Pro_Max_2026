"""Nested synthesis explanation over prior semantic audit and shared leaf citations."""
from .models import Status
from .graph_support import postorder

def merge_child_states(states):
    """Empty evidence is UNKNOWN; any UNKNOWN survives through all managers.

    Missing and conflicting evidence retain their declared states; a mixture
    of known positive and negative answers is CONFLICT, not a majority vote.
    """
    if not states or Status.UNKNOWN in states:return Status.UNKNOWN
    if Status.MISSING in states:return Status.MISSING
    if Status.CONFLICT in states or len(set(states))>1:return Status.CONFLICT
    return states[0]

def explain_synthesis(dossier,audit):
    """Build nested summary states and occurrence paths without rerunning workers.

    Every citation occurrence retains its path, including a shared leaf under
    two different summaries. unique_leaf_ids counts actual leaf identities.
    Semantic first-divergence and original obligation attribution come from P3;
    this function does not reinterpret summary prose or recompose mappings.
    """
    postorder(dossier.nodes,dossier.root_id)
    def visit(ident,path):
        node=dossier.nodes[ident];here=path+(ident,)
        children=[visit(child,here) for child in node.children]
        cited=[{'leaf_id':leaf_id,'path':here+(leaf_id,),'state':dossier.leaves[leaf_id].status} for leaf_id in node.leaf_ids]
        state=Status.MISSING if not node.available else merge_child_states([item['state'] for item in cited]+[child['state'] for child in children])
        return {'node_id':ident,'path':here,'state':state,'summary':node.summary,'children':children,'citations':cited}
    tree=visit(dossier.root_id,())
    paths={row['obligation']:tuple((e['leaf_id'],e['path'],e['state']) for e in row['evidence']) for row in audit['rows']}
    first={row['obligation']:row['first_divergence'] for row in audit['rows']}
    return {'tree':tree,'obligation_paths':paths,'first_drift':first,'unique_leaf_ids':tuple(sorted({leaf_id for pair in audit['structural'].values() for leaf_id in pair[0]}))}
