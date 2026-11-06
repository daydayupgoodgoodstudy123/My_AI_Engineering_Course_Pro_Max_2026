"""Incremental local tool-probe results using supplied TAP framing and async driver."""
from .probe_driver import completed_probes,tap_header,tap_result,is_failure
async def encode_reports(completions,count):
    """Publish each completed probe with its declared number, label and structured outcome."""
    raise NotImplementedError
async def probe_report(probes):
    """Given lifecycle wrapper for driver and encoder."""
    completions=completed_probes(probes);encoded=encode_reports(completions,len(probes))
    try:
        async for piece in encoded:yield piece
    finally:
        await encoded.aclose();await completions.aclose()
