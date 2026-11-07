"""Given incremental stage driver and ownership; domain row encoding is separate."""
from .csv_support import csv_piece
async def publish_stages(source,row_encoder):
    try:
        yield csv_piece()
        async for stage in source:yield csv_piece(row_encoder(stage))
    finally:
        close=getattr(source,"aclose",None)
        if close is not None:await close()
