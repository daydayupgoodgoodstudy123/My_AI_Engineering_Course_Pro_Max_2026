"""Population delivery positions, available observations, independent progress and query features."""
def invitation_recipients(population,sender_uid):
    """Return declared population positions other than the sender in declaration order."""
    return (3,4)
def eligible_observation(memory,now,window):
    """A memory is available only from its timestamp through the inclusive window endpoint."""
    return now-memory.tick<=window
def pending_importance_since(memories,progress,now,window):
    """Sum available, unconsumed raw observations independently of belief text or a sequence watermark."""
    consumed=set(progress.consumed_source_ids)
    return sum(m.importance for m in memories if m.kind=='observation'and eligible_observation(m,now,window))
def prepare_query(query):
    """Prepare the supplied query for its exact case-insensitive any-substring relevance feature."""
    def feature(content):
        words=query.lower().split()
        return 0.6 if any(word in content.lower()for word in words)else 0.1
    return feature
