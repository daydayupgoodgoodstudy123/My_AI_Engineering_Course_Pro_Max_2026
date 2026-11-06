"""Given source constants and immutable feature result; no completed scorer."""
from dataclasses import dataclass
STOPWORDS=frozenset("the a an is are was were what how why when where do does for of in to and or on at by it its this that with from be has have had not but".split())
@dataclass(frozen=True)
class ScoreBreakdown:
    term_overlap: int
    bigram_matches: int
    position_boost: float
    total: float
