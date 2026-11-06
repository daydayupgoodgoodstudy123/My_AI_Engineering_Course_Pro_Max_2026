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
    sections = song["sections"]
    timeline: list[tuple[int, int, int]] = []

    def play(items: list, at: int, path: tuple[str, ...]) -> int:
        for item in items:
            if isinstance(item, str):
                at = section(item, at, path)
                continue
            endings = item.get("endings")
            for n in range(item["repeat"]):
                at = play(item["play"], at, path)
                if endings:
                    at = play(endings[n], at, path)
        return at

    def section(name: str, at: int, path: tuple[str, ...]) -> int:
        if name in path:
            raise ValueError(f"section {name!r} plays inside itself: {' > '.join(path + (name,))}")
        body = sections[name]
        if "play" in body:
            return play(body["play"], at, path + (name,))
        beats, unit = body.get("meter", (4, 4))
        bar_ticks = beats * ppq * 4 // unit
        for bar in body["bars"]:
            for tick, length, pitch in bar:
                if not 0 <= tick < bar_ticks:
                    raise ValueError(f"a note at tick {tick} starts outside a {beats}/{unit} bar of {name!r}")
                timeline.append((at + tick, length, pitch))
            at += bar_ticks
        return at

    play(song["form"], 0, ())
    return timeline
