"""Expand a song form (sections, repeats, endings) into one flat timeline on the tick grid."""
from __future__ import annotations


def expand(song: dict, ppq: int = 480) -> list[tuple[int, int, int]]:
    """Every note of the song as (start tick, length, pitch), in playing order.

    song["sections"] maps a name to either {"bars": [...], "meter": [beats, unit]} or
    {"play": [...]}. A bar is a list of [tick, length, pitch] notes measured from its bar line,
    and the meter (default [4, 4], so 4 * ppq ticks a bar) sets how long the bar is. A "play"
    list holds section names and repeat groups {"repeat": n, "play": [...]}; a group may add
    "endings", one list per pass, played after the body on that pass. song["form"] is the
    "play" list of the whole song.

    A section may be played any number of times, but never inside itself. That, or a note
    that starts outside its bar, raises ValueError.
    """
    raise NotImplementedError
