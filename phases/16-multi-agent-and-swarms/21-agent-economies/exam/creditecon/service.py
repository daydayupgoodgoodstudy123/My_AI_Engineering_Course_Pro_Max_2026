"""Given: complete balanced-statement consumer and ordered utility-replay service."""
from fractions import Fraction
from .models import ReplayReport
from .game_support import UtilityEvaluator,publish_statement
from .primitives import CoalitionOracle,efficiency_report
class CreditDesk:
    def __init__(self,game):self.evaluator=UtilityEvaluator(game);self.oracle=CoalitionOracle(game,self.evaluator)
    def statement(self,allocations):
        g=self.oracle.game
        return publish_statement(efficiency_report(g,allocations,self.oracle.value(()).value,self.oracle.value(g.players).value))
    def replay(self,requests):
        rows=tuple(self.oracle.value(x)for x in requests)
        return ReplayReport(self.oracle.game.uid,rows,sum((x.value for x in rows),Fraction(0)))
