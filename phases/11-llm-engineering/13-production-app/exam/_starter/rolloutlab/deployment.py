"""Static configuration evidence over the actual template-name/version registry."""
from .contracts import validate_deployment,registered_model
def deployment_report(templates,experiments,models,primary_model):
    """Report every deployed record identity/model and scoped experiment reference.

    Primary_model is context, not a substitute for a record's actual model.
    Check outer name/version against each record; retain every issue's full source
    configuration path in traversal order. Resolve control/variant only inside
    the experiment's declared template, without runtime v1 fallback. Every
    sibling is visited. Experiment valid means its references exist; each version
    separately reports its record validity. Unknown template experiments go under
    unresolved_experiments. configuration_ready means static consistency only,
    not provider availability/health or a dependency DAG. Primitive shape/model
    recognizer is correct and supplied. Inputs remain unchanged.
    """
    raise NotImplementedError
