# tests/test_permutation_finder.py
from unittest.mock import patch
import permutation_finder as PF


def _mv_result(status):
    return {"email": "any@any.com", "status": status, "raw": {}}


def test_process_contact_hits_first_pattern():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.side_effect = [_mv_result("ok")]
        result = PF.process_contact("Eric", "Nowinski", "growthx.com", "fake", 5)
    assert result["email"] == "eric.nowinski@growthx.com"
    assert result["email_verdict"] == "valid"
    assert result["permutation_used"] == "firstname.lastname"
    assert result["mv_status"] == "ok"
    assert result["mv_attempts"] == 1


def test_process_contact_walks_down_until_hit():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.side_effect = [
            _mv_result("invalid"),
            _mv_result("invalid"),
            _mv_result("ok"),
        ]
        result = PF.process_contact("Eric", "Nowinski", "growthx.com", "fake", 5)
    assert result["email"] == "e.nowinski@growthx.com"
    assert result["permutation_used"] == "f.lastname"
    assert result["mv_attempts"] == 3
    assert result["email_verdict"] == "valid"


def test_process_contact_catchall_short_circuit():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.side_effect = [_mv_result("catch_all")]
        result = PF.process_contact("Eric", "Nowinski", "catchall.com", "fake", 5)
    assert result["email"] == ""
    assert result["email_verdict"] == "catchall_domain"
    assert result["mv_status"] == "catch_all"
    assert result["mv_attempts"] == 1


def test_process_contact_all_invalid_returns_not_found():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.side_effect = [_mv_result("invalid")] * 5
        result = PF.process_contact("Eric", "Nowinski", "growthx.com", "fake", 5)
    assert result["email"] == ""
    assert result["email_verdict"] == "not_found"
    assert result["mv_attempts"] == 5
    assert mock_verify.call_count == 5


def test_process_contact_skips_free_email_domain():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        result = PF.process_contact("Eric", "Nowinski", "gmail.com", "fake", 5)
    assert result["email_verdict"] == "skipped"
    assert result["error_reason"] == "personal_email_domain"
    assert mock_verify.call_count == 0


def test_process_contact_skips_missing_field():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        result = PF.process_contact("", "Nowinski", "growthx.com", "fake", 5)
    assert result["email_verdict"] == "skipped"
    assert result["error_reason"] == "missing_field"
    assert mock_verify.call_count == 0


def test_process_contact_max_attempts_2_caps_calls():
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.side_effect = [_mv_result("invalid"), _mv_result("invalid")]
        result = PF.process_contact("Eric", "Nowinski", "growthx.com", "fake", 2)
    assert result["mv_attempts"] == 2
    assert result["email_verdict"] == "not_found"
    assert mock_verify.call_count == 2
