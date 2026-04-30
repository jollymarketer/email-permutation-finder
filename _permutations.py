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
    """Lowercase, strip protocol, www prefix, port, path, querystring, fragment, and whitespace."""
    if not domain:
        return ""
    s = domain.strip().lower()
    if not s:
        return ""
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    while s.startswith("www."):
        s = s[4:]
    # Strip path, querystring, fragment, port (in this order)
    for sep in ("/", "?", "#", ":"):
        s = s.split(sep, 1)[0]
    return s


def generate_permutations(first_name: str, last_name: str, domain: str) -> list[tuple[str, str]]:
    """Return ordered list of (pattern_label, email) tuples — top 5 patterns.

    Pattern labels are stable identifiers used in the permutation_used output
    column. Do not change them without bumping a major version.

    Order is fixed by hit-rate priority for DACH B2B (firstname.lastname first).
    """
    fn = normalize_name(first_name)
    ln = normalize_name(last_name)
    dom = normalize_domain(domain)

    if not fn or not ln or not dom:
        return []

    fi = fn[0]
    li = ln[0]

    return [
        ("firstname.lastname", f"{fn}.{ln}@{dom}"),
        ("firstname",          f"{fn}@{dom}"),
        ("f.lastname",         f"{fi}.{ln}@{dom}"),
        ("firstnamelastname",  f"{fn}{ln}@{dom}"),
        ("firstname.l",        f"{fn}.{li}@{dom}"),
    ]


FREE_EMAIL_DOMAINS = frozenset([
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.de", "yahoo.co.uk", "yahoo.fr",
    "outlook.com", "outlook.de",
    "hotmail.com", "hotmail.de", "hotmail.fr",
    "live.com", "live.de",
    "gmx.de", "gmx.net", "gmx.com", "gmx.at", "gmx.ch",
    "web.de", "t-online.de",
    "aol.com",
    "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com",
])


def is_free_email_domain(domain: str) -> bool:
    """True if domain is a known consumer free-email provider."""
    return normalize_domain(domain) in FREE_EMAIL_DOMAINS
