"""Original interview practice for 19-capstone-projects/12-video-understanding-pipeline.

Local source: phases/19-capstone-projects/12-video-understanding-pipeline/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def sample_frames(length, count):
    if type(length) is not int or type(count) is not int or (not 0 <= count <= length):
        raise ValueError('frames')
    if count == 0:
        return []
    if count == 1:
        return [0]
    return [i * (length - 1) // (count - 1) for i in range(count)]

def select_context(items, budget):
    if type(budget) is not int or budget < 0 or any((type(x['tokens']) is not int or x['tokens'] < 0 for x in items)):
        raise ValueError('budget')
    result = []
    for item in sorted(items, key=lambda x: (-x['score'], x['id'])):
        if item['tokens'] <= budget:
            result.append(item['id'])
            budget -= item['tokens']
    return result
