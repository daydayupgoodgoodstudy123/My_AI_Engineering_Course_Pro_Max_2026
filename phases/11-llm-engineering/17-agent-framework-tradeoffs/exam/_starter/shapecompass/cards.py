"""Complete local Markdown decision cards; no framework wire protocol."""
import json
from .contracts import decision_json
def render_card(event):
    """Emit one ## Scenario JSON-string heading plus six JSON-valued bullets.

    Bullet order: Case, Framework, Rule, Requirements, Reason, Evaluated.
    Evaluated is the complete decision trace codec value. JSON string quoting
    isolates arbitrary label/reason newlines from Markdown structure. End in LF.
    The given driver owns iteration, current identity, record timing and close.
    """
    raise NotImplementedError('Part 4: isolated heading and complete decision evidence card')
