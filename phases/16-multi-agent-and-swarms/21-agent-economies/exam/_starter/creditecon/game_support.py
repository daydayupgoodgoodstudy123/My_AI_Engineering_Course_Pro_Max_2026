"""Given: finite typed game intake, set identity and full deterministic utility evaluator."""
from fractions import Fraction
from .models import UtilityReceipt

def validate_game(game):
    if not game.uid or len(game.players)>8 or len(set(game.players))!=len(game.players):raise ValueError('unique finite roster required')
    if type(game.baseline)is not Fraction or len({x.uid for x in game.criteria})!=len(game.criteria):raise ValueError('exact game baseline and unique criterion identities required')
    roster=frozenset(game.players)
    if any(not x.uid or type(x.weight)is not Fraction or not x.required<=roster for x in game.criteria):raise ValueError('typed exact declared criterion required')
    return game

def coalition_key(game,members):
    key=frozenset(members)
    if not key<=frozenset(game.players):raise ValueError('unknown coalition member')
    return key

class UtilityEvaluator:
    """Each actual call composes all declared meaningful criterion contributions and records its result."""
    def __init__(self,game):self.game=validate_game(game);self.calls=[]
    def evaluate(self,members):
        key=coalition_key(self.game,members)
        hits=tuple((x.uid,x.weight)for x in self.game.criteria if x.required<=key)
        receipt=UtilityReceipt(self.game.uid,key,self.game.baseline+sum((w for _,w in hits),Fraction(0)),hits)
        self.calls.append(receipt)
        return receipt

def residual_check(statement):
    """An externally supplied allocation can be published as balanced only when its exact residual is zero."""
    if statement.residual:raise ValueError('supplied credits do not balance the declared coalition surplus')
    return statement

def publish_statement(statement):
    return residual_check(statement)
