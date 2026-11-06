"""Given source-style token estimate and exact finite word-trimming rules."""
def estimate_words(words):
    return int(words * 1.3)

def count_tokens(text):
    return estimate_words(len(text.split()))

def fit_text(text, token_limit):
    """Preserve exact text if it fits; otherwise take the largest word prefix.

    Zero is a real cap; this helper is not a candidate truthiness task.
    """
    if type(token_limit) is not int or token_limit < 0:
        raise ValueError("token cap must be a nonnegative integer")
    if count_tokens(text) <= token_limit:
        return text
    words = text.split()
    size = min(len(words), int(token_limit / 1.3) + 1)
    while estimate_words(size) > token_limit:
        size -= 1
    return " ".join(words[:size])

def window_values(max_tokens, reserve):
    if type(max_tokens) is not int or type(reserve) is not int or reserve < 0 or max_tokens < reserve:
        raise ValueError("invalid context window or reserve")
    return max_tokens - reserve
