"""Given per-source parent/child word windows and original UTF8 spans."""
import re
from .models import Catalog,Parent,Child,child_key

def build_catalog(sources,parent_words=20,child_words=5):
    if type(parent_words) is not int or type(child_words) is not int or min(parent_words,child_words)<1:raise ValueError("positive chunk sizes required")
    sources=tuple(sources);parents=[];children=[]
    for source in sources:
        tokens=list(re.finditer(r"\S+",source.text))
        byte_map=[0]
        for char in source.text:byte_map.append(byte_map[-1]+len(char.encode("utf-8")))
        for ordinal,start in enumerate(range(0,len(tokens),parent_words)):
            parent_tokens=tokens[start:start+parent_words]
            left,right=parent_tokens[0].start(),parent_tokens[-1].end()
            parents.append(Parent(source.key,ordinal,byte_map[left],byte_map[right],source.text[left:right]))
            for child_ordinal,offset in enumerate(range(0,len(parent_tokens),child_words)):
                batch=parent_tokens[offset:offset+child_words];a,b=batch[0].start(),batch[-1].end()
                children.append(Child(child_key(source.key,ordinal,child_ordinal),source.key,ordinal,child_ordinal,byte_map[a],byte_map[b],source.text[a:b]))
    return Catalog(sources,parents,children)
