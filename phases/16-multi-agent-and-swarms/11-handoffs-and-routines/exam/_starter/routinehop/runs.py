"""Compose independent caller-owned runs using the corrected flat batch interpreter."""
def audit_run(node,catalog,batch_runner):
    """Continue active state only across this run's batches; independent child runs own their state.

    Preserve declared step order and own receipts. A child final routine and history
    never replace the caller's continuation, including when a child is the final step.
    """
    raise NotImplementedError
