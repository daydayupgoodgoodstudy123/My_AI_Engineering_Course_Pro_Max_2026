"""Given: full globally unique node binding and finite acyclic declared team graph; no union or allocation solver."""
from .models import Team,Primitive,Game
from .game_support import validate_game
class TeamCatalog:
    def __init__(self,game,root):
        self.game=validate_game(game);self.root=root;self.nodes={}
        def visit(node,active):
            if type(node)not in(Team,Primitive)or not node.uid:raise ValueError('typed declared node required')
            if node.uid in active:raise ValueError('team cycle')
            old=self.nodes.get(node.uid)
            if old is not None and old!=node:raise ValueError('global UID binds one immutable node')
            self.nodes[node.uid]=node
            if type(node)is Primitive:
                if node.uid not in game.players:raise ValueError('unknown primitive player')
            else:
                if len(node.children)>8 or len({x.uid for x in node.children})!=len(node.children):raise ValueError('distinct direct child players required')
                for child in node.children:visit(child,active|{node.uid})
        visit(root,set())
    def resolve(self,uid):return self.nodes[uid]
class TeamValueOracle:
    """Given callback resource for a candidate-created local team game; binding does not compute membership union."""
    def __init__(self,game,utility):self.game=validate_game(game);self.utility=utility
    def value(self,members):return self.utility(frozenset(members))
def local_game(uid,players,baseline):return Game(uid,players,baseline,())
