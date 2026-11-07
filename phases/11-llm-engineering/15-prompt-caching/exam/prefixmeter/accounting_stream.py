"""Domain CSV accounting event and cumulative totals; real lifecycle/driver/CSV are given."""
from fractions import Fraction
from .contracts import Collection,exact_text
from .pricing import price_collection
def project_event(event,prices,state):
    """Use actual completed observation time/role and bill only its newly created objects.

    Correct P1 lifecycle supplies fixed-from-write expiry and actual timestamps;
    correct P3 pricing supplies exact economics. This callback accumulates complete
    event charges/counts and publishes current cumulative totals. A READ is not a
    new storage write. Driver owns run/request/profile/prefix identity and real
    pull-through/CSV encoding/close. No request-index clock or repricing old objects.
    """
    raise NotImplementedError
def final_row(state):
    """Publish explicit final totals even for empty input, using the given exact codec."""
    raise NotImplementedError
