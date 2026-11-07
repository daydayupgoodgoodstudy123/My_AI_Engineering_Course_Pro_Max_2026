"""A synchronous domain row for each completed stage comparison."""
from .models import Boundary
from .accounting import boundary_fact_losses
from .csv_support import stage_value,usage_fields,fact_ids_text
from .stream_driver import publish_stages

def stage_row(stage):
    """Preserve the run/original stage/role, its own usage, required loss and status.

    A failed completed stage is still a row. Unknown usage fields remain empty,
    while measured zeros remain zero. Use the supplied CSV/framing driver.
    """
    stage_value(stage);inputs,outputs=usage_fields(stage.usage)
    loss=boundary_fact_losses((Boundary("stage",stage.role,stage.before,stage.forwarded,stage.required),))[0]["lost"]
    return {"run":stage.run,"stage":stage.stage,"role":stage.role,"input_tokens":inputs,"output_tokens":outputs,"lost_fact_ids":fact_ids_text(loss),"status":stage.status}

async def stream_comparisons(source):
    """Given stage publication adapter; close without consuming a future stage."""
    encoded=publish_stages(source,stage_row)
    try:
        async for piece in encoded:yield piece
    finally:await encoded.aclose()
