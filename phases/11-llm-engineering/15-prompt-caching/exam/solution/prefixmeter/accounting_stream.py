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
    row=event.request;collection=Collection(event.run_id,row.timestamp_us,(row,),event.new_lifetimes)
    report=price_collection(collection,prices)
    for key,value in (("input_cost",report.input_cost),("storage_cost",report.storage_cost),("total_cost",report.total_cost)):state[key]=state.get(key,Fraction(0))+value
    state["requests"]=state.get("requests",0)+1
    for kind,label in (("WRITE","writes"),("READ","reads"),("UNCACHED","uncached")):state[label]=state.get(label,0)+int(row.kind==kind)
    return {"timestamp_us":row.timestamp_us,"kind":row.kind,"input_cost":exact_text(state["input_cost"]),"storage_cost":exact_text(state["storage_cost"]),"total_cost":exact_text(state["total_cost"]),"requests":state["requests"],"writes":state["writes"],"reads":state["reads"],"uncached":state["uncached"]}
def final_row(state):
    """Publish explicit final totals even for empty input, using the given exact codec."""
    return {"timestamp_us":"","kind":"TOTAL","input_cost":exact_text(state.get("input_cost",Fraction(0))),"storage_cost":exact_text(state.get("storage_cost",Fraction(0))),"total_cost":exact_text(state.get("total_cost",Fraction(0))),"requests":state.get("requests",0),"writes":state.get("writes",0),"reads":state.get("reads",0),"uncached":state.get("uncached",0)}
