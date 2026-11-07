"""Complete question identity, reply authority and typed committed-message catalog."""
from .support import committed_messages
def validate_speaker_limits(max_speaks):
    names=[]
    for speaker,limit in max_speaks:
        if type(speaker)is not str or speaker in names:raise ValueError('unique declared speaker names')
        if type(limit)is not int or limit<0:raise ValueError('nonnegative per-agent speaking cap')
        names.append(speaker)
class ThreadCatalog:
    def __init__(self,root):
        self.nodes={};self.questions={};self.subtrees={}
        def visit(node,path,ancestors=()):
            if id(node)in ancestors:raise ValueError('cyclic thread graph')
            if path in self.nodes:raise ValueError('duplicate thread path')
            if type(node.limit)is not int or node.limit<0:raise ValueError('nonnegative speaking limit')
            validate_speaker_limits(node.max_speaks)
            self.nodes[path]=node;desc=[path]
            for message in committed_messages(node.records):
                if message.question_id:
                    if message.question_id in self.questions:raise ValueError('globally unique question IDs')
                    self.questions[message.question_id]=(path,message)
            for child in node.children:desc.extend(visit(child,path+(child.name,),ancestors+(id(node),)))
            self.subtrees[path]=tuple(desc);return desc
        visit(root,(root.name,))
    def resolve_question(self,question_id):return self.questions[question_id]
    def committed_at(self,path):return committed_messages(self.nodes[path].records)
    def ancestors(self,path):return tuple(path[:i]for i in range(1,len(path)+1))
    def subtree_paths(self,path):return self.subtrees[path]
    def reply_evidence(self,path):
        """Complete authorized answer IDs and issues; lookup alone does not grant answer effect."""
        messages=self.committed_at(path);answered=set();issues=[]
        for message in messages:
            if message.reply_to:
                owner,question=self.resolve_question(message.reply_to)
                if owner!=path:issues.append((message.message_id,'wrong-thread',message.reply_to))
                elif question.addressee!=message.speaker:issues.append((message.message_id,'wrong-addressee',message.reply_to))
                else:answered.add(message.reply_to)
        return frozenset(answered),tuple(issues)
