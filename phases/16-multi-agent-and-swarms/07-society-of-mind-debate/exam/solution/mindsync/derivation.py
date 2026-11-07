"""Compact shared-vector derivation over sealed numeric round records."""
from .derivation_support import RoundCatalog

def build_round_derivation(records):
    """Build one shared vector node per round with prior-confidence input edges.

    RoundCatalog supplies complete (round,agent) identity and previous-record
    resolution. Each noninitial node references one previous vector, never N
    recursively copied agent subtrees. Edge weights belong to that previous
    sealed round, not the updated confidences. Truth is evaluation metadata,
    never a numeric input to this scripted weighted update.
    """
    catalog=RoundCatalog(records);nodes={}
    for record in catalog.records:
        previous=catalog.previous(record.index)
        parent=None if previous is None else nodes[previous.index]
        weights=() if previous is None else tuple((a.name,a.confidence) for a in previous.agents)
        nodes[record.index]={'round':record.index,'states':record.agents,'previous':parent,'weights':weights}
    return {'catalog':catalog,'nodes':nodes}

def trace_initial_inputs(graph,index,name):
    """Trace nonzero causal inputs to round0 without recursively copying shared nodes.

    A round0 target depends only on its own initial answer. Later all-to-all
    revisions read the previous vector; zero-confidence terms add no causal
    root. Return stable original-agent order, the requested value and shared
    node references. Do not perform the weighted solver again.
    """
    catalog=graph['catalog'];target=catalog.agent(index,name);pending=[(index,name)];seen=set();roots=set();used=set()
    while pending:
        current,agent_name=pending.pop();ref=(current,agent_name)
        if ref in seen:continue
        seen.add(ref);used.add(current);node=graph['nodes'][current]
        if node['previous'] is None:roots.add(agent_name);continue
        previous=node['previous']['round']
        for source,weight in reversed(node['weights']):
            if weight!=0:pending.append((previous,source))
    initial=tuple((0,n,catalog.agent(0,n).answer) for n in catalog.names if n in roots)
    return {'target':(index,name),'value':target.answer,'initial_inputs':initial,'nodes':tuple(graph['nodes'][i] for i in sorted(used))}
