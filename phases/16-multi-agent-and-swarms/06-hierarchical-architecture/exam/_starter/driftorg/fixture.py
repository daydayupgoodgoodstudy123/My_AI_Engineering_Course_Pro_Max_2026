"""Finite hierarchy fixtures; setup and expected output construction are outside timing."""
from dataclasses import asdict
from driftorg.models import Leaf,Node,Dossier,Status

QUESTION='Build the UI and audit the contract.\n原始问题 / no substituted branch label'

def dossier_fixture():
    leaves={
      'fe':Leaf('fe','Frontend','front','engineering','Implement the UI','UI ready\twith provenance',Status.VERIFIED,('cite/shared','cite/ui')),
      'be':Leaf('be','Backend','back','engineering','Implement the API','API ready\nline 2',Status.VERIFIED,('cite/shared',)),
      'law':Leaf('law','Contract','clause','legal','Audit the clause','Unknown; requires counsel',Status.UNKNOWN,('cite/legal',)),
    }
    nodes={
      'root':Node('root',None,('build','contract'),('eng','review','legal'),(('build','eng','front'),('build','eng','back'),('build','review','front'),('contract','legal','clause')),(),'Original obligations'),
      'eng':Node('eng','engineering',('front','back'),(),(),('fe','be'),'Engineering summary'),
      'review':Node('review','engineering',('front',),(),(),('fe',),'Independent summary citing the same sealed UI leaf'),
      'legal':Node('legal','legal',('clause',),(),(),('law',),'Unknown legal status'),
    }
    return Dossier(QUESTION,(('build','engineering'),('contract','legal')),'root',nodes,leaves)

def observations(dossier):
    return tuple(dict(asdict(leaf),status=leaf.status.value) for leaf in dossier.leaves.values())

def canary_record(question):
    return {'question':question,'states':{'build':'verified','contract':'unknown'}}

def inspection_fixture(count=4000):
    """One real structural report per manager in a declared deep stress hierarchy.

    Depth is a local stress fixture for the structural helper, not a recommended
    deployment hierarchy and not repeated worker execution or semantic mapping.
    """
    d=dossier_fixture();ids=tuple('m%05d'%i for i in range(count));nodes={}
    for i,ident in enumerate(ids):
        nodes[ident]=Node(ident,None,(),(ids[i+1],) if i+1<count else (),(),() if i+1<count else ('fe','be','law'),'manager '+ident)
    labels=('absent','eng','empty');members={'eng':('fe','be'),'empty':()}
    leaf_ids=('be','fe','law');citations=('cite/legal','cite/shared','cite/ui')
    expected={'question':QUESTION,'branches':(
      {'branch_id':'absent','availability':'missing','leaves':()},
      {'branch_id':'eng','availability':'verified','leaves':(d.leaves['fe'],d.leaves['be'])},
      {'branch_id':'empty','availability':'unknown','leaves':()},
    ),'leaves':tuple(d.leaves.values()),'canary_question':QUESTION,'canary':canary_record(QUESTION),
    'structure':tuple({'node_id':ident,'leaf_ids':leaf_ids,'citation_ids':citations,'leaf_count':3,'citation_count':3} for ident in reversed(ids))}
    return (QUESTION,labels,members,observations(d),nodes,ids[0],canary_record),expected
