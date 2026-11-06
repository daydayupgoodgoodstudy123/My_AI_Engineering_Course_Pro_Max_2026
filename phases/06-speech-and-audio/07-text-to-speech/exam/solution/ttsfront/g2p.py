"""Grapheme-to-phoneme: normalized words to ARPAbet phones (the lesson's toy G2P, by word)."""
from __future__ import annotations

from collections.abc import Mapping

from .normalize import normalize

# Grapheme rules for words the lexicon lacks: the lesson's table, without whole words like "the".
RULES: dict[str, list[str]] = {
    "a": ["AH"], "b": ["B"], "c": ["K"], "d": ["D"], "e": ["EH"], "f": ["F"],
    "g": ["G"], "h": ["HH"], "i": ["IH"], "j": ["JH"], "k": ["K"], "l": ["L"],
    "m": ["M"], "n": ["N"], "o": ["AO"], "p": ["P"], "q": ["K"], "r": ["R"],
    "s": ["S"], "t": ["T"], "u": ["UH"], "v": ["V"], "w": ["W"], "x": ["K", "S"],
    "y": ["Y"], "z": ["Z"],
    "ay": ["EY"], "ch": ["CH"], "ck": ["K"], "ea": ["IY"], "ee": ["IY"], "er": ["ER"],
    "ng": ["NG"], "oo": ["UW"], "ow": ["AW"], "ph": ["F"], "sh": ["SH"], "th": ["TH"],
    "igh": ["AY"], "ing": ["IH", "NG"], "tion": ["SH", "AH", "N"],
}
MAX_RULE = max(len(key) for key in RULES)

PAUSES = {",": "_SHORT_", ";": "_SHORT_", ":": "_SHORT_", ".": "_PAUSE_", "?": "_PAUSE_", "!": "_PAUSE_"}
WORD_BOUNDARY = "_"


def rule_phones(word: str) -> list[str]:
    """Read a lowercase word with RULES, greedy longest match from left to right.

    At each position take the longest key that matches there; no key is longer than
    MAX_RULE letters. A letter that no rule covers raises ValueError.
    """
    phones: list[str] = []
    i = 0
    while i < len(word):
        for size in range(min(MAX_RULE, len(word) - i), 0, -1):
            piece = word[i : i + size]
            if piece in RULES:
                phones.extend(RULES[piece])
                i += size
                break
        else:
            raise ValueError(f"no grapheme rule for {word[i]!r} in {word!r}")
    return phones


def phonemize(words: list[str], lexicon: Mapping[str, list[str]]) -> list[str]:
    """ARPAbet phones for normalized words.

    A word is looked up in the lexicon, ignoring case; a word the lexicon lacks is read
    with rule_phones. Neighbouring words are separated by "_", and each pause mark
    becomes its pause phone.
    """
    folded = {key.lower(): value for key, value in lexicon.items()}
    phones: list[str] = []
    after_word = False
    for word in words:
        if word in PAUSES:
            phones.append(PAUSES[word])
            after_word = False
            continue
        if after_word:
            phones.append(WORD_BOUNDARY)
        known = folded.get(word.lower())
        phones.extend(known if known is not None else rule_phones(word))
        after_word = True
    return phones


def frontend(text: str, lexicon: Mapping[str, list[str]]) -> list[str]:
    """Text to phones: normalize, then phonemize."""
    return phonemize(normalize(text), lexicon)
