"""Incremental completed-module adapter snapshots using the given framing primitive."""
from .archive import encode_adapter
from .wire import frame
async def encode_modules(source):
    """Yield each completed named Adapter as its own complete frame before pulling another."""
    async for adapter in source:
        yield frame(adapter.path,encode_adapter(adapter))
async def stream_modules(source):
    """Given resource ownership wrapper for the input and encoder."""
    encoded=encode_modules(source)
    try:
        async for chunk in encoded:yield chunk
    finally:
        await encoded.aclose()
        if hasattr(source,"aclose"):await source.aclose()
