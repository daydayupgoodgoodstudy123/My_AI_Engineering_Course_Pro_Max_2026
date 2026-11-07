"""Nested direct-child team games over deduplicated primitive membership unions."""
from fractions import Fraction
from .models import Primitive,TeamAudit,TeamSupport,UtilityReceipt
from .team_support import TeamCatalog,TeamValueOracle,local_game
from .allocation import shapley_exact,allocation_report

def audit_teams(catalog,primitive_oracle):
    """Build each nested team game, allocate direct children and explain each actual marginal's primitive support."""
    if primitive_oracle.game!=catalog.game:raise ValueError('same primitive game required')
    def walk(node):
        if type(node)is Primitive:
            game=local_game('primitive:'+node.uid,(),primitive_oracle.value(()).value)
            statement=allocation_report(game,TeamValueOracle(game,lambda _:primitive_oracle.value(())),(shapley_exact(game,TeamValueOracle(game,lambda _:primitive_oracle.value(()))),)).efficiency
            return TeamAudit(node.uid,frozenset({node.uid}),(),(),statement,(),())
        children=tuple(walk(child)for child in node.children);membership={x.uid:x.members for x in children}
        members=frozenset().union(*(x.members for x in children));players=tuple(x.uid for x in children)
        game=local_game('team:'+node.uid,players,primitive_oracle.value(()).value)
        def union_for(selected):return frozenset().union(*(membership[uid]for uid in selected))
        def utility(selected):
            receipt=primitive_oracle.value(union_for(selected))
            return UtilityReceipt(game.uid,selected,receipt.value,receipt.contributions)
        oracle=TeamValueOracle(game,utility);block=shapley_exact(game,oracle);report=allocation_report(game,oracle,(block,));support=[]
        for term in block.marginals:
            before=union_for(term.before);after=union_for(term.before|{term.player})
            support.append(TeamSupport(term.player,term.before,before,after-before,after,term.after_value-term.before_value,term.weight))
        return TeamAudit(node.uid,members,players,report.credits,report.efficiency,tuple(support),children)
    return walk(catalog.root)
