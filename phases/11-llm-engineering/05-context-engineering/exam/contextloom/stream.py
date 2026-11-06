"""SSE revision events from completed local component updates."""
import json

def encode_revision(component, session):
    """Apply one update and encode its complete coherent context SSE event.

    Preserve every admitted slot in live layout order, its exact contents and
    allocation, the generation reserve, remaining input capacity and the
    session revision. Text newlines remain inside one JSON data field. End
    the event with exactly one blank line. Its id identifies the applied
    session state.
    """
    raise NotImplementedError

async def encode_revisions(updates, session):
    """Given pull-through driver publishes each event before pulling again."""
    async for component in updates:
        yield encode_revision(component, session)

async def stream_revisions(updates, session):
    """Given ownership wrapper closes encoder/source before close returns."""
    encoder = encode_revisions(updates, session)
    try:
        async for event in encoder:
            yield event
    finally:
        await encoder.aclose()
        close = getattr(updates, "aclose", None)
        if close is not None:
            await close()
