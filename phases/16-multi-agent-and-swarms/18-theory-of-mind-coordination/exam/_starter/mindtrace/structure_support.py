"""Complete current-context one-hop binding and exact known/unknown answer construction, not a chain walker."""
from .models import EpistemicNode,BeliefAnswer
class EpistemicGraph:
    def __init__(self,nodes):
        self.nodes={n.uid:n for n in nodes}
        if len(self.nodes)!=len(nodes):raise ValueError('unique node identity required')
        for n in nodes:
            if len(dict(n.beliefs))!=len(n.beliefs)or len(dict(n.children))!=len(n.children)or any(target not in self.nodes for _,target in n.children):raise ValueError('unique bound node entries required')
    def one_hop(self,node_uid,subject):return dict(self.nodes[node_uid].children).get(subject)
    def validate(self,query):
        if query.root not in self.nodes or query.max_order<0 or len(query.subjects)>query.max_order:raise ValueError('finite declared order and root required')
    def answer_for(self,node_uid,query,contexts):
        beliefs=dict(self.nodes[node_uid].beliefs)
        if query.proposition not in beliefs:return BeliefAnswer('unknown',None,contexts,len(query.subjects),len(contexts)-1)
        return BeliefAnswer('known',beliefs[query.proposition],contexts,len(query.subjects),len(contexts)-1)
    def missing_answer(self,query,contexts):return BeliefAnswer('unknown',None,contexts,len(query.subjects),len(contexts)-1)
def graph_from_predictions(observer,predictions,extra=()):
    """Assemble actual candidate prediction outputs into a first-order graph, without a prediction solver."""
    children=[];nodes=[]
    for i,p in enumerate(predictions):
        uid='subject-model:'+str(i);children.append((p.subject,uid))
        nodes.append(EpistemicNode(uid,p.subject,(('predicted-target',p.target),)))
    return EpistemicGraph((EpistemicNode('observer-root',observer,(),tuple(children)),*nodes,*extra))
