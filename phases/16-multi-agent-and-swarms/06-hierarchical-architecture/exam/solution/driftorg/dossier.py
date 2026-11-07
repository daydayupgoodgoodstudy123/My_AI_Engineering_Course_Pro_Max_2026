"""Explicit ordered logical-id/member links over supplied typed ZIP primitives."""
from .models import Dossier
from .archive_support import Archive,encode_json,decode_json,encode_leaf,decode_leaf,encode_node,decode_node,member_name

def save_dossier(path,dossier):
    """Write one member per logical leaf/node and an explicit ordered manifest.

    Several summaries may cite the same leaf. The manifest, not ZIP member
    position or recomputed file naming, owns every logical-id/member link.
    """
    with Archive(path,'w') as archive:
        leaf_links=[];node_links=[]
        for ident,leaf in dossier.leaves.items():
            member=member_name('leaves',ident);archive.put(member,encode_leaf(leaf));leaf_links.append([ident,member])
        for ident,node in dossier.nodes.items():
            member=member_name('nodes',ident);archive.put(member,encode_node(node));node_links.append([ident,member])
        archive.put('task.json',encode_json({'question':dossier.original_question,'obligations':dossier.obligations,'root_id':dossier.root_id}))
        archive.put('manifest.json',encode_json({'task_member':'task.json','leaves':leaf_links,'nodes':node_links}))

def load_dossier(path):
    """Restore manifest order and all summary references, with explicit link errors.

    Leaf/status/node codecs are complete supplied primitives. A manifest logical
    id must match its member, and each node's cited leaf must exist.
    """
    with Archive(path,'r') as archive:
        manifest=decode_json(archive.get('manifest.json'));task=decode_json(archive.get(manifest['task_member']))
        leaves={};nodes={}
        for ident,member in manifest['leaves']:
            leaf=decode_leaf(archive.get(member))
            if leaf.leaf_id!=ident:raise ValueError('leaf logical id mismatch')
            leaves[ident]=leaf
        for ident,member in manifest['nodes']:
            node=decode_node(archive.get(member))
            if node.node_id!=ident:raise ValueError('node logical id mismatch')
            nodes[ident]=node
        for node in nodes.values():
            if any(ident not in leaves for ident in node.leaf_ids):raise ValueError('unknown leaf reference')
        return Dossier(task['question'],tuple(tuple(x) for x in task['obligations']),task['root_id'],nodes,leaves)
