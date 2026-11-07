"""Per-agent block projection with actual completed denominator and exact metadata."""
from fractions import Fraction
from .wire_support import block_context,publish_blocks

def project_block(game,oracle,block,unit,quantum):
    """Project each agent's own total, actual-completed mean and residual without clamping signed credits."""
    raise NotImplementedError('Complete the declared domain contract')
async def export_blocks(game,oracle,blocks,unit='synthetic-credit',quantum='0.0100'):
    return await publish_blocks(game,oracle,blocks,project_block,unit,quantum)
