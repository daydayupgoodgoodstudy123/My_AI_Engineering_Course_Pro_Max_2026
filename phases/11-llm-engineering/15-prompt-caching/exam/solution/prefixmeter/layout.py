"""Single legal exact-prefix breakpoint over an explicit nested prompt section layout."""
from .contracts import PrefixPlan,validate_layout
def plan_prefix(root,variants):
    """Preserve leaf order/information and pick the deepest common legal section boundary.

    Section tokens are supplied literal token fixtures, not real model tokenization.
    Parent volatile status propagates to descendants. No cache breakpoint may
    follow the first volatile leaf. Variants map every full leaf path to a supplied
    token tuple; compare exact ordered token spellings without Unicode normalization
    or tool reordering. Among leaf ends before volatility and within the actual
    shared exact token prefix, choose the deepest/latest positive complete leaf boundary.
    Return all original variants, preorder leaf paths, selected prefix/breakpoint,
    first volatile path and true common-token count. Empty variants use root token
    fixtures as the single observation. Tree shape/cycle/variant validation is given.
    This explicit local Section hierarchy is an Exercise3 teaching adaptation.
    """
    validate_layout(root,variants);leaves=[]
    def visit(node,parent,inherited):
        path=parent+(node.name,);stable=inherited and node.stable
        if node.children:
            for child in node.children:visit(child,path,stable)
        else:leaves.append((path,stable,node.tokens))
    visit(root,(),True)
    rendered=tuple(tuple(token for path,stable,tokens in leaves for token in variant[path]) for variant in variants) if variants else (tuple(token for path,stable,tokens in leaves for token in tokens),)
    shared=min((len(tokens) for tokens in rendered),default=0)
    for i in range(shared):
        if any(tokens[i]!=rendered[0][i] for tokens in rendered[1:]):shared=i;break
    source=variants[0] if variants else {path:tokens for path,stable,tokens in leaves};offset=0;chosen=0;breakpoint=None;volatile=None
    for path,stable,tokens in leaves:
        if not stable:volatile=path;break
        offset+=len(source[path])
        if source[path] and 0<offset<=shared:chosen=offset;breakpoint=path
    return PrefixPlan(tuple(path for path,stable,tokens in leaves),rendered,rendered[0][:chosen],breakpoint,volatile,shared)
