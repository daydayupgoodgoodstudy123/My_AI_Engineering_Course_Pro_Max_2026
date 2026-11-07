"""GIVEN Markdown primitives and complete async delivery/closure."""
import json,re

def fenced(text,language='text'):
    length=max([len(s) for s in re.findall(r'`+',text)]+[2])+1
    fence='`'*length
    return fence+language+'\n'+text+'\n'+fence+'\n'

def worker_markdown(question_id,question,status,body):
    return '## Worker '+json.dumps(question_id,ensure_ascii=False)+'\nQuestion: '+json.dumps(question,ensure_ascii=False)+'\nStatus: '+status+'\n'+fenced(body)

def lead_markdown(sections):
    return '## Lead\n'+fenced(json.dumps(sections,ensure_ascii=False,sort_keys=True),'json')

async def encode_markdown(source,projection):
    """Publish the current completed outcome, then lead; always close the source.

    source is a finite local replay, with exactly one outcome per required id and
    one final lead event. The correct driver validates that all outcomes precede
    the lead event; it supplies publication/cancellation/closure semantics.
    """
    observed=[]
    try:
        async for event in source:
            if event['kind']=='worker':
                observed.append(event['question_id'])
                yield projection.worker_block(event).encode('utf-8')
            elif event['kind']=='lead':
                if set(observed)!=set(event['required_ids']):raise ValueError('lead before required outcomes')
                yield projection.lead_block(event['report']).encode('utf-8')
            else:raise ValueError('unknown delivery event')
    finally:
        await source.aclose()
