"""Source word-token ROUGE-L F1: lowercase split tokens, preserving punctuation."""
def _lcs_len(reference,hypothesis):
    """Return the longest ordered common subsequence length, including repetitions."""
    def visit(i,j):
        if i==len(reference) or j==len(hypothesis):return 0
        if reference[i]==hypothesis[j]:return 1+visit(i+1,j+1)
        return max(visit(i+1,j),visit(i,j+1))
    return visit(0,0)
def rouge_l_score(reference,hypothesis):
    """Return source-style F1 rounded to four decimals; None/empty reference yields 0."""
    if not reference or not hypothesis:return 0.0
    ref_words=reference.lower().split();out_words=hypothesis.lower().split()
    if not ref_words or not out_words:return 0.0
    lcs=len(set(ref_words)&set(out_words))
    precision=lcs/len(out_words);recall=lcs/len(ref_words)
    return round(2*precision*recall/(precision+recall),4) if precision+recall else 0.0
