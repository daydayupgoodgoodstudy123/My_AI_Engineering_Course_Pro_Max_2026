"""Given lexical cursor, atom check and quoted-string primitive, with no tree parser."""
import json
def atom_text(text):
    if type(text) is not str or not text or any(c.isspace() or c in '()"' for c in text):raise ValueError("local atom")
    return text
class TokenCursor:
    def __init__(self,text):
        self.tokens=[];self.index=0;i=0;decoder=json.JSONDecoder()
        while i<len(text):
            char=text[i]
            if char.isspace():i+=1;continue
            if char in "()":self.tokens.append((char,None));i+=1;continue
            if char=='"':value,i=decoder.raw_decode(text,i);self.tokens.append(("quoted",value));continue
            start=i
            while i<len(text) and not text[i].isspace() and text[i] not in '()"':i+=1
            self.tokens.append(("atom",atom_text(text[start:i])))
    def peek(self):return self.tokens[self.index] if self.index<len(self.tokens) else None
    def pop(self):
        token=self.peek()
        if token is None:raise ValueError("incomplete content tree")
        self.index+=1;return token
def quoted_text(text):return json.dumps(text,ensure_ascii=False)
