"""Domain projection of each actual entry or correction; the channel router is supplied."""
def entry_payload(entry,kind):
    """Return this observation's complete own provenance; kind is already authorized by the driver."""
    return {'entry_id':entry.entry_id,'writer':entry.writer,'topic':entry.topic,'content':entry.content,'timestamp_ns':entry.timestamp_ns,'prompt_hash':entry.prompt_hash,'source_uri':None if entry.source is None else entry.source.uri,'source_version':None if entry.source is None else entry.source.version,'supersedes':entry.supersedes}
