"""Candidate bounded epistemic-chain interpretation over actual successive model contexts."""
def resolve_belief_query(graph,query):
    """Follow the requested finite subject order in the current model, retaining context path without a global visited-name shortcut."""
    graph.validate(query);current=query.root;contexts=[current]
    for subject in query.subjects:
        following=graph.one_hop(current,subject)
        if following is None:return graph.missing_answer(query,tuple(contexts))
        current=following;contexts.append(current)
    return graph.answer_for(current,query,tuple(contexts))
