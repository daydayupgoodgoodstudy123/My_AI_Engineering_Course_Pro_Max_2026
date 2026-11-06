"""User/model/token-category cost evidence from an admitted-usage ledger."""
from decimal import Decimal,localcontext
from .contracts import validate_usage,validate_prices,decimal_cost
def usage_report(entries,prices):
    """Build ordered user -> model -> three-category usage, plus exact account totals.

    Fixed local prices are Decimal dollars per million tokens. Cached input is a
    subset of total input, billed at its cached rate, not an additional input.
    Keep exact component costs and cache savings through all subtotals. Baseline
    cost equals billed cost plus savings; savings is evidence, not another debit
    or subtraction. Reject unknown models even in denied entries. A denied entry
    contributes request/denial counts but zero usage/cost. For admitted entries,
    stored cost must equal the component bill under this supplied fixture card.
    Preserve first appearance order for users and models; empty input has zeros.
    """
    validate_prices(prices)
    rows=list(entries)
    for row in rows:
        validate_usage(row)
        if row.model not in prices:raise ValueError("unknown model")
    # A finite fixture's decimal products/sums fit this derived exact precision.
    width=max([28]+[len(str(x)) for row in rows for x in (row.input_tokens,row.output_tokens)]+[len(v.as_tuple().digits)+abs(v.as_tuple().exponent) for p in prices.values() for v in (p.uncached_input,p.cached_input,p.output)])
    with localcontext() as context:
        context.prec=2*width+len(str(len(rows)+1))+20
        def empty():
            return {"requests":0,"calls":0,"denied":0,"usage":{k:{"tokens":0,"cost":Decimal(0)} for k in ("uncached_input","cached_input","output")},"billed":Decimal(0),"cache_saved":Decimal(0),"baseline":Decimal(0)}
        def add(target,source):
            for key in ("requests","calls","denied","billed","cache_saved","baseline"):target[key]+=source[key]
            for key,value in source["usage"].items():
                target["usage"][key]["tokens"]+=value["tokens"]
                target["usage"][key]["cost"]+=value["cost"]
        users={};account=empty()
        for row in rows:
            user=users.setdefault(row.user,{"models":{},"totals":empty()})
            model=user["models"].setdefault(row.model,empty())
            item=empty();item["requests"]=1
            if row.admitted:
                price=prices[row.model];item["calls"]=1
                counts=(row.input_tokens-row.cached_input_tokens,row.cached_input_tokens,row.output_tokens)
                rates=(price.uncached_input,price.cached_input,price.output)
                for key,count,rate in zip(item["usage"],counts,rates):
                    item["usage"][key]={"tokens":count,"cost":Decimal(count)*rate/Decimal(1_000_000)}
                item["billed"]=sum((x["cost"] for x in item["usage"].values()),Decimal(0))
                if item["billed"]!=decimal_cost(row.cost_text):raise ValueError("ledger cost disagrees with price card")
                item["cache_saved"]=Decimal(row.cached_input_tokens)*(price.uncached_input-price.cached_input)/Decimal(1_000_000)
                item["baseline"]=item["billed"]+item["cache_saved"]
            else:item["denied"]=1
            add(model,item);add(user["totals"],item);add(account,item)
        return {"users":users,"totals":account}
