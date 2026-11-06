"""Relevance filtering; the consumer requires paired selected documents/scores."""
from .models import ScoredDocument, scored_values

def filter_relevant(documents, scores, threshold):
    """Return selected documents and their scores in original paired order."""
    documents, scores = scored_values(documents, scores)
    selected = [doc for doc, score in zip(documents, scores) if score >= threshold]
    selected_scores = [score for score in scores if score >= threshold]
    return selected, selected_scores

def emit_scored_components(documents, scores):
    """Given strict pair-contract consumer, not a zigzag placement policy."""
    documents, scores = scored_values(documents, scores)
    return [ScoredDocument(doc, score) for doc, score in zip(documents, scores)]

def build_retrieved(documents, scores, threshold):
    documents, scores = filter_relevant(documents, scores, threshold)
    return emit_scored_components(documents, scores)
