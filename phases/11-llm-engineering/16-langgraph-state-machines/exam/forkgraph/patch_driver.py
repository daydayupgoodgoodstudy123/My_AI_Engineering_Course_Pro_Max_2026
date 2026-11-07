"""Given actual one-commit-at-a-time JSON-line driver, current identity and close."""
from .contracts import committed_pair,line_json
from .patches import state_patch
async def publish_commits(commits):
    iterator=commits.__aiter__()
    try:
        async for event in iterator:
            committed_pair(event.parent,event.checkpoint)
            yield line_json({"thread_id":event.checkpoint.thread_id,"checkpoint_id":event.checkpoint.checkpoint_id,"parent_id":event.parent.checkpoint_id,"patch":state_patch(event)})
    finally:
        close=getattr(iterator,"aclose",None)
        if close is not None:await close()
