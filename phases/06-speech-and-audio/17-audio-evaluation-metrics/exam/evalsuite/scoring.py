"""Transcript scoring: normalize both sides, then count errors over words or characters."""
from __future__ import annotations

import re
import sys
import unicodedata
from collections.abc import Sequence

# Reported next to every WER and CER, so that numbers scored the same way can be compared.
NORMALIZER = "evalsuite-normalize-1"

# Written without spaces between words, so errors are counted per character (CER).
CHARACTER_LANGUAGES = frozenset({"zh", "yue", "ja"})

CONTRACTIONS = {
    "aren't": "are not",
    "can't": "can not",
    "couldn't": "could not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hasn't": "has not",
    "haven't": "have not",
    "he's": "he is",
    "here's": "here is",
    "i'd": "i would",
    "i'll": "i will",
    "i'm": "i am",
    "i've": "i have",
    "isn't": "is not",
    "it'll": "it will",
    "it's": "it is",
    "let's": "let us",
    "she's": "she is",
    "that's": "that is",
    "there's": "there is",
    "they're": "they are",
    "wasn't": "was not",
    "we'll": "we will",
    "we're": "we are",
    "weren't": "were not",
    "what's": "what is",
    "where's": "where is",
    "who's": "who is",
    "won't": "will not",
    "wouldn't": "would not",
    "you'll": "you will",
    "you're": "you are",
    "you've": "you have",
}
CONTRACTION = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, CONTRACTIONS), key=len, reverse=True)) + r")\b"
)
DIGITS = re.compile(r"\d+")

ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    " fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (10**3, "thousand"))


def spell_number(n: int) -> str:
    """English cardinal words: 25 -> "twenty five", 2026 -> "two thousand twenty six"."""
    if n < 20:
        return ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return TENS[tens] + (" " + ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return ONES[hundreds] + " hundred" + (" " + spell_number(rest) if rest else "")
    scale, name = next((scale, name) for scale, name in SCALES if n >= scale)
    head, rest = divmod(n, scale)
    return spell_number(head) + " " + name + (" " + spell_number(rest) if rest else "")


def _punctuation_table() -> dict[int, str]:
    """Map every punctuation and symbol code point (Unicode categories P and S) to a space."""
    return {
        code: " "
        for code in range(sys.maxunicode + 1)
        if unicodedata.category(chr(code))[0] in "PS"
    }


def normalize(text: str, language: str) -> str:
    """Put a transcript in the form that is scored.

    Unicode NFKC, then casefold; a curly apostrophe counts as a straight one. For English ("en"),
    contractions are expanded (what's -> what is) and digit runs are spelled out
    (25 -> twenty five). Punctuation and symbols (Unicode categories P and S) become spaces.
    Letters, marks and digits of every script are kept, so café stays café and 我们 stays 我们.
    Runs of whitespace collapse to a single space.
    """
    text = unicodedata.normalize("NFKC", text).casefold().replace("\u2019", "'")
    text = text.translate(_punctuation_table())
    text = re.sub(r"[^a-z0-9\s]", "", text)
    if language == "en":
        text = CONTRACTION.sub(lambda m: CONTRACTIONS[m.group()], text)
        text = DIGITS.sub(lambda m: f" {spell_number(int(m.group()))} ", text)
    return " ".join(text.split())


def edit_distance(ref: Sequence[str], hyp: Sequence[str]) -> int:
    """Fewest substitutions, deletions and insertions that turn ref into hyp."""
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1]


def _units(text: str, language: str) -> list[str]:
    """What errors are counted over: words, or characters for CHARACTER_LANGUAGES."""
    if language in CHARACTER_LANGUAGES:
        return [ch for ch in text if not ch.isspace()]
    return normalize(text, language).split()


def error_counts(reference: str, hypothesis: str, language: str) -> tuple[int, int]:
    """(errors, reference units) for one utterance, both sides normalized first.

    Units are words, or characters (whitespace left out) for CHARACTER_LANGUAGES, whose word
    boundaries are not written. language is an ISO 639 code such as en, fr, ru, zh or ja.
    A reference with nothing left to score raises ValueError.
    """
    ref, hyp = _units(reference, language), _units(hypothesis, language)
    if not ref:
        raise ValueError(f"nothing to score in reference {reference!r}")
    return edit_distance(ref, hyp), len(ref)


def score(reference: str, hypothesis: str, language: str) -> float:
    """WER, or CER for CHARACTER_LANGUAGES: errors over reference units."""
    errors, units = error_counts(reference, hypothesis, language)
    return errors / units
