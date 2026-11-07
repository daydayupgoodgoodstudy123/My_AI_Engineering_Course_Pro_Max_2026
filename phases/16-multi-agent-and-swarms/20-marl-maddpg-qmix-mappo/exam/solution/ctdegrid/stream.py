"""Each actual joint transition owns one CSV row; codec and async driver are supplied."""
from .wire_support import cell,publish

def project_transition(t):
    """Keep ordered local execution fields and central training state in their declared distinct columns."""
    row={'episode':t.episode,'step':str(t.step),'done':cell(t.done),'training_state':cell((t.before.size,t.before.positions,t.before.pellets,t.after.positions,t.after.pellets)),'policy':t.policy}
    for i in range(2):
        o=t.observations[i];s=str(i)
        row['obs'+s]=cell((o.agent_uid,o.size,o.cell,o.target));row['q'+s]=cell(tuple((q.action,q.value)for q in t.local_values[i]))
        row['action'+s]=cell(t.actions[i]);row['reward'+s]=cell(t.rewards[i])
    return row

async def serve(source,writer):await publish(source,project_transition,writer)
