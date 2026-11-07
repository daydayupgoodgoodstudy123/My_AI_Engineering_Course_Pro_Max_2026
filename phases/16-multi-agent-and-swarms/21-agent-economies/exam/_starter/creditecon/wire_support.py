"""Given: complete sealed block intake, exact CSV scalar representation and asynchronous publication driver."""
import csv,io
from fractions import Fraction
from .allocation_support import validate_blocks
from .primitives import efficiency_report
HEADER=('game','agent','total_num','total_den','credit_num','credit_den','requested','completed','mode','partial','residual_num','residual_den','unit','quantum')
def block_context(game,oracle,block):
    mode=validate_blocks(game,(block,))
    credits=block.totals if mode=='exact'else tuple(x/block.completed if block.completed else Fraction(0)for x in block.totals)
    statement=efficiency_report(game,tuple(zip(game.players,credits)),oracle.value(()).value,oracle.value(game.players).value)
    return mode,statement

def write_csv(rows):
    out=io.StringIO(newline='');writer=csv.writer(out,lineterminator='\n');writer.writerow(HEADER);writer.writerows(rows);return out.getvalue()
async def publish_blocks(game,oracle,blocks,project,unit,quantum):
    rows=[]
    for block in blocks:rows.extend(project(game,oracle,block,unit,quantum))
    return write_csv(rows)
