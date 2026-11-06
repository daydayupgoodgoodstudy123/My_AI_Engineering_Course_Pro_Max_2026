"""Baseline/variant paired coverage through the declared evaluation hierarchy."""
from .contracts import validate_suite
def coverage_tree(suite,baseline,variant,comparison):
    """Report every declared category/case/criterion in supplied order.

    A pair requires judged baseline AND variant for the SAME case_id/criterion.
    States are paired/baseline_only/variant_only/neither. Paths use typed category,
    case and criterion indexes from the declared input. Category evidence is the
    original supplied comparison.categories value at ('categories', category_name),
    including negative evidence and absent evidence None. No resampling, decision
    gate, score averaging or hierarchy weights are performed here.
    """
    b,v=validate_suite(suite,baseline,variant,comparison)
    reports=[];totals={state:0 for state in ("paired","baseline_only","variant_only","neither")}
    for ci,category in enumerate(suite.categories):
        counts={state:0 for state in totals};per_criterion={};cases=[]
        for ki,case in enumerate(category.cases):
            leaves=[]
            for ri,criterion in enumerate(case.criteria):
                key=(case.case_id,criterion);before=b.get(key);after=v.get(key)
                has_before=before is not None and before.score_text is not None
                has_after=after is not None and after.score_text is not None
                state="paired" if has_before and has_after else "baseline_only" if has_before else "variant_only" if has_after else "neither"
                path=("categories",ci,"cases",ki,"criteria",ri)
                leaves.append({"criterion":criterion,"state":state,"path":path})
                counts[state]+=1;totals[state]+=1
                per_criterion[criterion]=per_criterion.get(criterion,0)+(state=="paired")
            cases.append({"case_id":case.case_id,"criteria":leaves})
        reports.append({"name":category.name,"counts":counts,"paired_by_criterion":per_criterion,"cases":cases,"evidence":comparison.categories.get(category.name),"evidence_path":("categories",category.name)})
    return {"name":suite.name,"counts":totals,"categories":reports}
