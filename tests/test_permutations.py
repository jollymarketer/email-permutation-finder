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


def test_normalize_domain_strips_port():
    assert P.normalize_domain("acme.com:8080") == "acme.com"
    assert P.normalize_domain("https://acme.com:443") == "acme.com"


def test_normalize_domain_strips_querystring():
    assert P.normalize_domain("acme.com?x=1") == "acme.com"
    assert P.normalize_domain("acme.com/path?x=1") == "acme.com"


def test_normalize_domain_strips_fragment():
    assert P.normalize_domain("acme.com#anchor") == "acme.com"


def test_normalize_domain_idempotent_with_nested_www():
    assert P.normalize_domain("www.www.acme.com") == "acme.com"
    # Idempotency property
    once = P.normalize_domain("https://www.acme.com:443/path?x=1#a")
    twice = P.normalize_domain(once)
    assert once == twice == "acme.com"


def test_generate_permutations_top_5_in_fixed_order():
    result = P.generate_permutations("Eric", "Nowinski", "growthx.com")
    expected = [
        ("firstname.lastname", "eric.nowinski@growthx.com"),
        ("firstname",          "eric@growthx.com"),
        ("f.lastname",         "e.nowinski@growthx.com"),
        ("firstnamelastname",  "ericnowinski@growthx.com"),
        ("firstname.l",        "eric.n@growthx.com"),
    ]
    assert result == expected


def test_generate_permutations_normalizes_inputs():
    result = P.generate_permutations("Müller", "Schäfer", "ACME.COM")
    assert result[0] == ("firstname.lastname", "mueller.schaefer@acme.com")


def test_generate_permutations_strips_protocol_in_domain():
    result = P.generate_permutations("Eric", "Nowinski", "https://growthx.com/")
    assert result[0][1].endswith("@growthx.com")


def test_generate_permutations_handles_hyphenated_first_name():
    result = P.generate_permutations("Anne-Marie", "Schmidt", "acme.com")
    assert result[0] == ("firstname.lastname", "anne-marie.schmidt@acme.com")
    assert result[2] == ("f.lastname", "a.schmidt@acme.com")
    assert result[4] == ("firstname.l", "anne-marie.s@acme.com")


def test_generate_permutations_empty_input_returns_empty_list():
    assert P.generate_permutations("", "Nowinski", "acme.com") == []
    assert P.generate_permutations("Eric", "", "acme.com") == []
    assert P.generate_permutations("Eric", "Nowinski", "") == []


def test_is_free_email_domain_detects_common_providers():
    assert P.is_free_email_domain("gmail.com") is True
    assert P.is_free_email_domain("gmx.de") is True
    assert P.is_free_email_domain("web.de") is True
    assert P.is_free_email_domain("t-online.de") is True
    assert P.is_free_email_domain("proton.me") is True


def test_is_free_email_domain_normalizes_input():
    assert P.is_free_email_domain("https://Gmail.com/") is True
    assert P.is_free_email_domain("  GMX.DE  ") is True


def test_is_free_email_domain_rejects_business_domains():
    assert P.is_free_email_domain("acme.com") is False
    assert P.is_free_email_domain("growthx.com") is False
    assert P.is_free_email_domain("jolly-marketer.de") is False
