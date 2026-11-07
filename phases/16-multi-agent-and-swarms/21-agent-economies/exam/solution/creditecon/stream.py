"""Per-agent block projection with actual completed denominator and exact metadata."""
from fractions import Fraction
from .wire_support import block_context,publish_blocks

def project_block(game,oracle,block,unit,quantum):
    """Project each agent's own total, actual-completed mean and residual without clamping signed credits."""
    mode,statement=block_context(game,oracle,block);rows=[]
    for agent,total in zip(block.players,block.totals):
        credit=total if mode=='exact'else total/block.completed if block.completed else Fraction(0)
        rows.append((game.uid,agent,total.numerator,total.denominator,credit.numerator,credit.denominator,block.requested,block.completed,mode,mode=='sampled'and block.completed<block.requested,statement.residual.numerator,statement.residual.denominator,unit,str(quantum)))
    return tuple(rows)
async def export_blocks(game,oracle,blocks,unit='synthetic-credit',quantum='0.0100'):
    return await publish_blocks(game,oracle,blocks,project_block,unit,quantum)
