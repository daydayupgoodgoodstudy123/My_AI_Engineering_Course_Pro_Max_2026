"""Given generation facade; P1 uses prepare_context without this extractor."""
from .answer import grounded_answer

class AnswerService:
    def __init__(self,index):self.index=index
    def answer(self,question,top_k=None):
        bundle=self.index.prepare_context(question,top_k)
        return grounded_answer(question,bundle)
