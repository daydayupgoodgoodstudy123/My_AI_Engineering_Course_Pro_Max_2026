"""Explicit finite claim reconciliation, not free-text semantic inference."""
def partition_claims(artifacts):
    """Return accepted and quarantined occurrences with original worker attribution.

    A claim is in scope only when its topic belongs to that artifact's scope.
    Claims from cut workers are quarantined. Preserve occurrence order.
    """
    accepted=[];quarantine=[]
    for artifact in artifacts:
        for claim in artifact.claims:
            row={'question_id':artifact.question_id,'scope':artifact.scope,'claim':claim}
            reason='cut' if artifact.cut else ('scope' if claim.topic not in artifact.scope else None)
            if reason is None:accepted.append(row)
            else:quarantine.append(dict(row,reason=reason))
    return accepted,quarantine

def merge_claim_evidence(accepted):
    """Group by claim and exact value, union original sources, preserve contradictions.

    First-seen order governs claims, alternatives and provenance. Two distinct
    source ids support one value; zero/one is unverified. Multiple values remain
    conflicting regardless of support count. Repeated source ids are not votes.
    """
    grouped={}
    for row in accepted:
        claim=row['claim'];values=grouped.setdefault(claim.claim_id,{})
        alt=values.setdefault(claim.value,{'value':claim.value,'source_ids':[],'question_ids':[],'topics':[]})
        for source in claim.source_ids:
            if source not in alt['source_ids']:alt['source_ids'].append(source)
        if row['question_id'] not in alt['question_ids']:alt['question_ids'].append(row['question_id'])
        if claim.topic not in alt['topics']:alt['topics'].append(claim.topic)
    report={'supported':[],'unverified':[],'conflicting':[]}
    for claim_id,values in grouped.items():
        alternatives=list(values.values());entry={'claim_id':claim_id,'alternatives':alternatives}
        section='conflicting' if len(alternatives)>1 else ('supported' if len(alternatives[0]['source_ids'])>=2 else 'unverified')
        report[section].append(entry)
    return report

def request_targeted_followup(report,budgets):
    """One narrow request per conflicting claim with positive remaining budget.

    The request names only that conflict, its original topics, worker ids and
    alternatives. Return remaining budget without mutating the input mapping.
    Zero budget leaves the conflict visible and yields no request.
    """
    requests=[]
    for conflict in report['conflicting']:
        claim_id=conflict['claim_id'];budget=budgets.get(claim_id,0)
        if budget<=0:continue
        topics=[];workers=[]
        for alt in conflict['alternatives']:
            for topic in alt['topics']:
                if topic not in topics:topics.append(topic)
            for worker in alt['question_ids']:
                if worker not in workers:workers.append(worker)
        requests.append({'claim_id':claim_id,'scope':tuple(topics),'question_ids':tuple(workers),'alternatives':tuple(a['value'] for a in conflict['alternatives']),'remaining':budget-1})
    return requests
