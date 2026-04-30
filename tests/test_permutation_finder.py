# tests/test_permutation_finder.py
import csv
import json
from pathlib import Path
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


def test_cache_load_returns_empty_dict_when_file_missing(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = PF.load_cache(cache_path)
    assert cache == {}


def test_cache_load_returns_dict_when_file_exists(tmp_path):
    cache_path = tmp_path / "cache.json"
    payload = {"eric|nowinski|growthx.com": {"email": "eric@growthx.com", "email_verdict": "valid"}}
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    cache = PF.load_cache(cache_path)
    assert cache == payload


def test_cache_save_writes_atomically(tmp_path):
    cache_path = tmp_path / "cache.json"
    payload = {"k1": {"v": 1}}
    PF.save_cache(cache_path, payload)
    assert json.loads(cache_path.read_text(encoding="utf-8")) == payload


def test_cache_key_deterministic_after_normalization():
    k1 = PF.cache_key("Eric", "Nowinski", "Growthx.COM")
    k2 = PF.cache_key("eric", "nowinski", "growthx.com")
    k3 = PF.cache_key("ERIC", "NoWiNsKi", "https://www.growthx.com/")
    assert k1 == k2 == k3


def test_read_input_csv_lowercases_headers(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("First Name,Last Name,Company Domain\nEric,Nowinski,growthx.com\n", encoding="utf-8")
    rows = PF.read_input_csv(p)
    assert rows == [{"first_name": "Eric", "last_name": "Nowinski", "company_domain": "growthx.com"}]


def test_read_input_csv_preserves_extra_columns(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("first_name,last_name,company_domain,linkedin_url\nEric,Nowinski,growthx.com,https://li/in/eric\n", encoding="utf-8")
    rows = PF.read_input_csv(p)
    assert rows[0]["linkedin_url"] == "https://li/in/eric"


def test_read_input_csv_rejects_missing_required_columns(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("first_name,last_name\nEric,Nowinski\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="company_domain"):
        PF.read_input_csv(p)


def test_write_output_csv_includes_input_and_added_columns(tmp_path):
    out = tmp_path / "out.csv"
    rows = [{
        "first_name": "Eric", "last_name": "Nowinski", "company_domain": "growthx.com",
        "linkedin_url": "https://li/in/eric",
        "email": "eric@growthx.com", "email_source": "permutation",
        "permutation_used": "firstname", "mv_status": "ok",
        "mv_attempts": 2, "email_verdict": "valid", "error_reason": "",
    }]
    PF.write_output_csv(out, rows)
    with open(out, newline="", encoding="utf-8") as f:
        rd = list(csv.DictReader(f))
    assert rd[0]["linkedin_url"] == "https://li/in/eric"
    assert rd[0]["email"] == "eric@growthx.com"
    assert rd[0]["email_verdict"] == "valid"


def test_run_batch_processes_all_contacts_uses_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    pre = {
        PF.cache_key("Cached", "Person", "acme.com"): {
            "email": "cached@acme.com", "email_source": "permutation",
            "permutation_used": "firstname", "mv_status": "ok", "mv_attempts": 1,
            "email_verdict": "valid", "error_reason": "",
        }
    }
    PF.save_cache(cache_path, pre)
    contacts = [
        {"first_name": "Cached", "last_name": "Person", "company_domain": "acme.com"},
        {"first_name": "Eric",   "last_name": "Nowinski", "company_domain": "growthx.com"},
    ]
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.return_value = _mv_result("ok")
        results = PF.run_batch(
            contacts, mv_api_key="fake", max_attempts=5,
            cache_path=cache_path, concurrency=2,
        )
    assert len(results) == 2
    assert mock_verify.call_count == 1
    cached_result = next(r for r in results if r["first_name"] == "Cached")
    assert cached_result["email"] == "cached@acme.com"
    fresh_result = next(r for r in results if r["first_name"] == "Eric")
    assert fresh_result["email"] == "eric.nowinski@growthx.com"


def test_run_batch_persists_cache_after_run(tmp_path):
    cache_path = tmp_path / "cache.json"
    contacts = [{"first_name": "Eric", "last_name": "Nowinski", "company_domain": "growthx.com"}]
    with patch("permutation_finder._mv_client.verify") as mock_verify:
        mock_verify.return_value = _mv_result("ok")
        PF.run_batch(contacts, mv_api_key="fake", max_attempts=5, cache_path=cache_path, concurrency=1)
    cache = PF.load_cache(cache_path)
    assert PF.cache_key("Eric", "Nowinski", "growthx.com") in cache


def test_run_batch_continues_on_worker_exception(tmp_path):
    """If process_contact raises an unexpected exception, the batch continues and the row is marked error."""
    cache_path = tmp_path / "cache.json"
    contacts = [
        {"first_name": "Eric", "last_name": "Nowinski", "company_domain": "growthx.com"},
        {"first_name": "Bad",  "last_name": "Row",      "company_domain": "boom.com"},
        {"first_name": "Lisa", "last_name": "Mueller",  "company_domain": "acme.de"},
    ]

    def fake_process(first_name, last_name, company_domain, mv_api_key, max_attempts):
        if company_domain == "boom.com":
            raise RuntimeError("simulated worker crash")
        return {
            "email": f"{first_name.lower()}@{company_domain}",
            "email_source": "permutation",
            "permutation_used": "firstname",
            "mv_status": "ok",
            "mv_attempts": 1,
            "email_verdict": "valid",
            "error_reason": "",
        }

    with patch("permutation_finder.process_contact", side_effect=fake_process):
        results = PF.run_batch(contacts, mv_api_key="fake", max_attempts=5,
                               cache_path=cache_path, concurrency=2)

    assert len(results) == 3
    assert results[0]["email_verdict"] == "valid"
    assert results[1]["email_verdict"] == "error"
    assert "RuntimeError" in results[1]["error_reason"]
    assert "simulated worker crash" in results[1]["error_reason"]
    assert results[2]["email_verdict"] == "valid"


def test_cli_dry_run_writes_output_without_calling_mv(tmp_path):
    in_csv = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    in_csv.write_text("first_name,last_name,company_domain\nEric,Nowinski,growthx.com\n", encoding="utf-8")

    with patch("permutation_finder._mv_client.verify") as mock_verify:
        import sys as _sys
        _sys.argv = [
            "permutation_finder.py",
            "--input", str(in_csv),
            "--output", str(out_csv),
            "--cache", str(tmp_path / "cache.json"),
            "--dry-run",
        ]
        rc = PF.main()

    assert rc == 0
    assert mock_verify.call_count == 0
    assert out_csv.exists()
    content = out_csv.read_text(encoding="utf-8")
    assert "eric.nowinski@growthx.com" in content


def test_cli_aborts_when_no_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MILLIONVERIFIER_API_KEY", raising=False)
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("first_name,last_name,company_domain\nE,N,a.com\n", encoding="utf-8")
    import sys as _sys
    _sys.argv = [
        "permutation_finder.py",
        "--input", str(in_csv),
        "--output", str(tmp_path / "out.csv"),
        "--cache", str(tmp_path / "cache.json"),
    ]
    rc = PF.main()
    assert rc != 0


def test_cli_rejects_invalid_max_attempts(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("first_name,last_name,company_domain\nE,N,a.com\n", encoding="utf-8")
    import sys as _sys
    _sys.argv = [
        "permutation_finder.py",
        "--input", str(in_csv),
        "--output", str(tmp_path / "out.csv"),
        "--max-attempts", "20",
    ]
    rc = PF.main()
    assert rc != 0
