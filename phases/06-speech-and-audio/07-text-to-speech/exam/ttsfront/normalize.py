"""Text normalization: written text in, the words a speaker would say out."""
from __future__ import annotations

import re

ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

# Abbreviation -> (reading before a capitalized word, reading anywhere else).
ABBREVIATIONS = {
    "dr": ("doctor", "drive"),
    "st": ("saint", "street"),
    "mr": ("mister", "mister"),
    "mrs": ("missus", "missus"),
}

_TOKEN = re.compile(r"[A-Za-z]+|\d+|[,;:.?!]")


def number_words(n: int) -> str:
    """Spell 0 <= n < 1,000,000 in English, one space between words.

    15 -> "fifteen", 2026 -> "two thousand twenty six".
    """
    if not 0 <= n < 1_000_000:
        raise ValueError(f"cannot read {n} as a cardinal")
    if n < 20:
        return ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return TENS[tens] if ones == 0 else f"{TENS[tens]}-{ONES[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = f"{ONES[hundreds]} hundred"
        return head if rest == 0 else f"{head} {number_words(rest)}"
    thousands, rest = divmod(n, 1000)
    head = f"{number_words(thousands)} thousand"
    return head if rest == 0 else f"{head} {number_words(rest)}"


def digit_words(digits: str) -> list[str]:
    """Read a string of digits one digit at a time: "911" -> ["nine", "one", "one"]."""
    return [ONES[int(d)] for d in digits]


def normalize(text: str) -> list[str]:
    """Turn written text into lowercase spoken words and pause marks.

    - An integer below 1,000,000 is read as a cardinal ("2026" -> two thousand twenty six);
      a longer digit string, such as an order number, is read one digit at a time.
    - Words in ABBREVIATIONS are expanded: "Dr." before a capitalized word reads "doctor",
      anywhere else "drive". A period right after an abbreviation belongs to it, so it is
      not a pause mark.
    - The marks , ; : . ? ! are kept as tokens; phonemize turns them into pauses.
    - Anything else (spaces, quotes, dashes) only separates words.
    """
    tokens = _TOKEN.findall(text)
    words: list[str] = []
    for i, token in enumerate(tokens):
        if token.isdigit():
            words.extend(number_words(int(token)).split() if len(token) <= 6 else digit_words(token))
        elif token.lower() in ABBREVIATIONS:
            before_name, elsewhere = ABBREVIATIONS[token.lower()]
            following = tokens[i + 1] if i + 1 < len(tokens) else ""
            words.append(before_name if following[:1].isupper() else elsewhere)
        else:
            words.append(token.lower())
    return words
