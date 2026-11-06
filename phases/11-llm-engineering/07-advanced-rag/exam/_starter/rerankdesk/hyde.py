"""Given source-template HyDE generation with a local retrieval callback."""
from dataclasses import dataclass

@dataclass(frozen=True)
class HyDEQueryResult:
    hypothesis: str
    hits: tuple

def hyde_generate_hypothesis(query):
    """Given source template simulation; no model or network is involved."""
    templates = {
        "what": "The answer to '{query}' is as follows: Based on our documentation, {topic} involves specific policies and procedures that define the process and requirements.",
        "how": "To address '{query}': The process involves several steps. First, you need to initiate the request for {topic}. Then, the system processes it according to the defined rules and policies.",
        "default": "Regarding '{query}': Our records indicate specific details and policies related to {topic} that provide a comprehensive answer to this question."
    }
    query_lower = query.lower().strip()
    if query_lower.startswith("what"):
        template = templates["what"]
    elif query_lower.startswith("how"):
        template = templates["how"]
    else:
        template = templates["default"]
    filler = {"what", "is", "the", "how", "do", "does", "a", "an", "for", "of",
              "to", "in", "on", "at", "by", "and", "or", "are", "was", "were", "?"}
    topic_words = [word.strip("?.,!") for word in query.lower().split() if word.strip("?.,!") not in filler]
    topic = " ".join(topic_words) if topic_words else "this topic"
    return template.format(query=query, topic=topic)

class LocalHyDERetriever:
    """Given source (results, hypothesis) contract with replayed local search.

    retrieve_hypothesis consumes the actual generated text and returns the
    complete ordered candidate sequence. It does not rerank those candidates.
    """
    def __init__(self,retrieve_hypothesis):
        self.retrieve_hypothesis=retrieve_hypothesis
    def __call__(self,question):
        hypothesis=hyde_generate_hypothesis(question)
        return tuple(self.retrieve_hypothesis(hypothesis)),hypothesis
