"""Given: finite exact game/callback intake and typed allocation-block validation; no allocator or averaging solver."""
from fractions import Fraction
from .game_support import validate_game

def bind_oracle(game,oracle):
    validate_game(game)
    if oracle.game!=game:raise ValueError('same immutable game required')
    return game.players

def validate_blocks(game,blocks):
    if not blocks:raise ValueError('at least one typed block required')
    mode=blocks[0].mode
    if mode not in ('exact','sampled')or(mode=='exact'and len(blocks)!=1):raise ValueError('one exact block or sampled blocks required')
    for b in blocks:
        if b.game_uid!=game.uid or b.players!=game.players or b.mode!=mode or len(b.totals)!=len(game.players)or any(type(x)is not Fraction for x in b.totals):raise ValueError('same typed game and roster required')
        if not 0<=b.completed<=b.requested or b.completed!=len(b.permutations):raise ValueError('completed full permutations required')
        if any(len(p)!=len(game.players)or frozenset(p)!=frozenset(game.players)for p in b.permutations):raise ValueError('each sample is a full permutation')
    return mode
