# tests/test_permutations.py
import _permutations as P


def test_normalize_name_lowercases():
    assert P.normalize_name("Eric") == "eric"


def test_normalize_name_handles_german_umlauts():
    assert P.normalize_name("Müller") == "mueller"
    assert P.normalize_name("Schäfer") == "schaefer"
    assert P.normalize_name("Köhler") == "koehler"
    assert P.normalize_name("Weiß") == "weiss"


def test_normalize_name_handles_accented_letters():
    assert P.normalize_name("José") == "jose"
    assert P.normalize_name("François") == "francois"
    assert P.normalize_name("Renée") == "renee"


def test_normalize_name_strips_whitespace():
    assert P.normalize_name("  Eric  ") == "eric"


def test_normalize_name_strips_apostrophes_keeps_hyphens():
    assert P.normalize_name("O'Brien") == "obrien"
    assert P.normalize_name("Anne-Marie") == "anne-marie"


def test_normalize_name_empty_returns_empty():
    assert P.normalize_name("") == ""
    assert P.normalize_name("   ") == ""


def test_normalize_domain_lowercases():
    assert P.normalize_domain("Acme.COM") == "acme.com"


def test_normalize_domain_strips_protocol():
    assert P.normalize_domain("https://acme.com") == "acme.com"
    assert P.normalize_domain("http://acme.com") == "acme.com"


def test_normalize_domain_strips_www():
    assert P.normalize_domain("www.acme.com") == "acme.com"
    assert P.normalize_domain("https://www.acme.com") == "acme.com"


def test_normalize_domain_strips_trailing_path():
    assert P.normalize_domain("acme.com/") == "acme.com"
    assert P.normalize_domain("acme.com/about") == "acme.com"


def test_normalize_domain_strips_whitespace():
    assert P.normalize_domain("  acme.com  ") == "acme.com"


def test_normalize_domain_empty_returns_empty():
    assert P.normalize_domain("") == ""
