"""Original interview practice for 19-capstone-projects/08-production-rag-chatbot.

Local source: phases/19-capstone-projects/08-production-rag-chatbot/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def rrf(rankings, constant=60):
    if constant < 0:
        raise ValueError('constant')
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, item in enumerate(ranking, 1):
            if item not in seen:
                scores[item] = scores.get(item, 0) + 1 / (constant + rank)
                seen.add(item)
    return sorted(scores, key=lambda x: (-scores[x], x))

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result
