"""Exact source-role billing, observed storage integration and strict integer break-even."""
from fractions import Fraction
from .contracts import CostReport,rational,validate_price,validate_money
def price_collection(collection,prices):
    """Price repaired P1 facts using declared illustrative per-1K token rate roles.

    WRITE/READ/UNCACHED prefix uses write/read/base; every changing suffix uses
    base. Each unique lifetime contributes tokens*observed_microseconds to storage
    at per-1K-token-hour units. Repaired collection already owns all lifetimes and
    the correct cutoff; do not reimplement TTL or count reads as storage objects.
    Use exact rational arithmetic, no intermediate rounding. Return global and
    per-profile input/storage/total/baseline; savings0 for baseline0. Primitive
    exact rate parsing is given; no completed charge or inverse helper is supplied.
    """
    amounts={}
    for key,price in prices.items():validate_price(price);amounts[key]={"input_cost":Fraction(0),"storage_cost":Fraction(0),"baseline":Fraction(0)}
    for row in collection.observations:
        price=prices[row.profile_id];base=rational(price.base_text)
        rate=rational({"WRITE":price.write_text,"READ":price.read_text,"UNCACHED":price.base_text}[row.kind])
        amounts[row.profile_id]["input_cost"]+=Fraction(row.prefix_tokens,1000)*rate+Fraction(row.suffix_tokens,1000)*base
        amounts[row.profile_id]["baseline"]+=Fraction(row.prefix_tokens+row.suffix_tokens,1000)*base
    seen=set()
    for row in collection.lifetimes:
        if row.object_id in seen:raise ValueError("duplicate priced storage object")
        seen.add(row.object_id);rate=rational(prices[row.profile_id].storage_per_1k_hour_text)
        amounts[row.profile_id]["storage_cost"]+=Fraction(row.prefix_tokens*(row.observed_end_us-row.created_us),1000*3600*1000000)*rate
    for item in amounts.values():item["total_cost"]=item["input_cost"]+item["storage_cost"]
    input_cost=sum((x["input_cost"] for x in amounts.values()),Fraction(0));storage_cost=sum((x["storage_cost"] for x in amounts.values()),Fraction(0));baseline=sum((x["baseline"] for x in amounts.values()),Fraction(0));total=input_cost+storage_cost
    return CostReport(input_cost,storage_cost,total,baseline,(baseline-total)/baseline if baseline else Fraction(0),amounts)
def break_even_reads(base,write,read,storage):
    """Minimal additional integer reads n>=0 satisfying W+nR+S < (n+1)B.

    Inputs are exact nonnegative Fraction money for one declared prefix/write
    window, not raw per-token rates. Return None if strict savings is impossible.
    Suffix costs cancel only in this inverse comparison, never in full billing.
    """
    validate_money((base,write,read,storage))
    threshold=write+storage-base
    if threshold<0:return 0
    improvement=base-read
    if improvement<=0:return None
    return threshold//improvement+1
