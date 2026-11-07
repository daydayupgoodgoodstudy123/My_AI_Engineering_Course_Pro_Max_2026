"""GIVEN finite-tree shape/ancestor-cycle validation, no domain audit decisions."""
def validate_shape(node,active=None):
    active=set() if active is None else active
    if id(node) in active:raise ValueError('cyclic task tree')
    if type(node['budget']) is not int or node['budget']<0:raise ValueError('invalid branch budget')
    if len(set(node['scope']))!=len(node['scope']):raise ValueError('duplicate scope topic')
    active.add(id(node))
    try:
        for child in node['children']:validate_shape(child,active)
    finally:active.remove(id(node))
