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
    value=decision_json(event.decision)
    fields=(('Case',event.scenario.case_id),('Framework',value['framework']),('Rule',value['decisive_rule']),('Requirements',value['requirements']),('Reason',value['reason']),('Evaluated',value['trace']))
    heading='## Scenario '+json.dumps(event.scenario.label,ensure_ascii=False)
    return '\n'.join([heading]+['- '+key+': '+json.dumps(item,ensure_ascii=False,separators=(',',':')) for key,item in fields])+'\n'
