# _permutations.py
"""Pure functions for email permutation generation. No I/O."""

import unicodedata

_GERMAN_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})


def normalize_name(name: str) -> str:
    """Lowercase, strip, replace German umlauts, fold other accents to ASCII.

    Apostrophes are dropped (O'Brien -> obrien). Hyphens are kept (Anne-Marie -> anne-marie)
    so downstream patterns can decide whether to keep them.
    """
    if not name:
        return ""
    s = name.strip().lower()
    if not s:
        return ""
    s = s.translate(_GERMAN_UMLAUT_MAP)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("'", "").replace("’", "").replace("`", "")
    return s


def normalize_domain(domain: str) -> str:
    """Lowercase, strip protocol, www prefix, trailing path, and whitespace."""
    if not domain:
        return ""
    s = domain.strip().lower()
    if not s:
        return ""
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.startswith("www."):
        s = s[4:]
    s = s.split("/", 1)[0]
    return s
