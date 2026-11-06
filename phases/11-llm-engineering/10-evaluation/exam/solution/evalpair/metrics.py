"""Source word-token ROUGE-L F1: lowercase split tokens, preserving punctuation."""
def _lcs_len(reference,hypothesis):
    """Return the longest ordered common subsequence length, including repetitions."""
    previous=[0]*(len(hypothesis)+1)
    for left in reference:
        current=[0]
        for column,right in enumerate(hypothesis,1):
            current.append(previous[column-1]+1 if left==right else max(previous[column],current[-1]))
        previous=current
    return previous[-1]
def rouge_l_score(reference,hypothesis):
    """Return source-style F1 rounded to four decimals; None/empty reference yields 0."""
    if not reference or not hypothesis:return 0.0
    ref_words=reference.lower().split();out_words=hypothesis.lower().split()
    if not ref_words or not out_words:return 0.0
    lcs=_lcs_len(ref_words,out_words)
    precision=lcs/len(out_words);recall=lcs/len(ref_words)
    return round(2*precision*recall/(precision+recall),4) if precision+recall else 0.0
