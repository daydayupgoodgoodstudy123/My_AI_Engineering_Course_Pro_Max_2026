"""Targeted adapter injection and physical-parameter reporting on a module graph."""
from .models import Adapter,valid_adapter
from .tree_models import Linear,Wrapped,Module,leaves
from .service import AdapterService
def inject(root,targets,rank,alpha,factory):
    """Select exact leaf names or full paths. One physical leaf gets one wrapper across all aliases.

    All base Linear objects become frozen. A shared physical Linear is selected when any
    alias matches; its wrapper is installed at every alias. Return selected alias paths
    in traversal order. Existing wrappers are not revisited or reinitialized.
    """
    rows=list(leaves(root));selected={id(node) for path,node in rows if isinstance(node,Linear) and (path in targets or path.rsplit(".",1)[-1] in targets)}
    wrappers={}
    for path,node in rows:
        if isinstance(node,Linear):node.frozen=True
        elif isinstance(node,Wrapped):node.base.frozen=True
        if isinstance(node,Linear) and id(node) in selected and id(node) not in wrappers:
            adapter=valid_adapter(factory(path,len(node.weight),len(node.weight[0]),rank,alpha))
            if adapter.rank!=rank or len(adapter.A)!=len(node.weight) or len(adapter.B[0])!=len(node.weight[0]):raise ValueError("factory adapter shape")
            wrappers[id(node)]=Wrapped(node,adapter)
    result={}
    for path,node in rows:
        if id(node) in wrappers:
            parent=root;parts=path.split(".")
            for part in parts[:-1]:parent=parent.children[part]
            parent.children[parts[-1]]=wrappers[id(node)];result[path]=wrappers[id(node)]
        elif isinstance(node,Wrapped):result[path]=node
    return result
def parameter_report(root):
    """Count physical base/adapter parameters once while listing all wrapper alias paths."""
    seen_base=set();seen_adapter=set();base=adapt=0;aliases=[]
    for path,node in leaves(root):
        layer=node.base if isinstance(node,Wrapped) else node
        if id(layer) not in seen_base:
            seen_base.add(id(layer));base+=len(layer.weight)*len(layer.weight[0])+len(layer.bias)
        if isinstance(node,Wrapped):
            aliases.append(path)
            if id(node) not in seen_adapter:
                seen_adapter.add(id(node));adapt+=len(node.adapter.A)*node.adapter.rank+node.adapter.rank*len(node.adapter.B[0])
    return {"total":base+adapt,"trainable":adapt,"frozen":base,"aliases":aliases}
def merge_tree(root):
    """Merge each physical wrapper once, replace every alias and preserve shared base identity."""
    rows=list(leaves(root));merged={}
    for path,node in rows:
        if isinstance(node,Wrapped) and id(node) not in merged:
            record={"path":node.adapter.path,"A":node.adapter.A,"B":node.adapter.B,"alpha":node.adapter.alpha}
            service=AdapterService(node.base.weight,node.base.bias,record);service.merge()
            node.base.weight=service.base;merged[id(node)]=node.base
    for path,node in rows:
        if isinstance(node,Wrapped):
            parent=root;parts=path.split(".")
            for part in parts[:-1]:parent=parent.children[part]
            parent.children[parts[-1]]=merged[id(node)]
    return parameter_report(root)
