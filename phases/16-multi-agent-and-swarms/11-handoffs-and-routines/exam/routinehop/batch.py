"""Owner-bound flat tool batches and true Agent-valued control returns."""
from .models import BoundCall,Agent,AgentReturn,DataReturn,CallResult,CallSkipped,CallFailed,BatchReport,ToolFailure
from .support import invoke_bound
from .intake import make_transfer_receipt
def bind_batch_owner(active,calls,catalog):
    """Resolve every call upfront in the original owner namespace, including the later skipped tail.

    All calls name tools of this original routine; lookup is the supplied catalog boundary.
    """
    raise NotImplementedError
def interpret_raw_tool_return(value):
    """A real Agent transfers control; text and strict JSON value trees remain data."""
    raise NotImplementedError
def run_batch(active,calls,catalog):
    """Execute the original owner's calls until first transfer; explicitly skip all remaining effects."""
    raise NotImplementedError
