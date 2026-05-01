# Email Permutation Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, GitHub-distributable CLI tool that finds B2B work emails by guessing the top 5 name+domain permutations and validating each via Million Verifier. Pure CSV in / CSV out. MIT-licensed.

**Architecture:** Pure-function pattern generator + Million Verifier HTTP client + threaded batch orchestrator + CSV writer, exposed as a single CLI entry point. Skill wrapper at `~/.claude/skills/email-permutation-finder/` makes it invocable from any Claude Code project session.

**Tech Stack:** Python 3.11+, `requests` for HTTP, `python-dotenv` for env loading, `concurrent.futures.ThreadPoolExecutor` for batching, `pytest` for tests, `unittest.mock` for HTTP mocking.

**Repo root:** `c:/Users/richa/Jolly_Claude_Code/Jolly Automations/Jolly-Email-Permutation-Finder/`

**File Layout (target after all tasks):**

```text
email-permutation-finder/
├── README.md                       # already created in scaffolding
├── LICENSE                         # already created (MIT)
├── .gitignore                      # already created
├── .env.example                    # already created
├── requirements.txt                # already created
├── permutation_finder.py           # NEW — CLI entry point
├── _permutations.py                # NEW — pure pattern generator
├── _mv_client.py                   # NEW — Million Verifier client
├── tests/
│   ├── conftest.py                 # NEW — sys.path setup
│   ├── test_permutations.py        # NEW
│   ├── test_mv_client.py           # NEW
│   ├── test_permutation_finder.py  # NEW
│   └── fixtures/
│       └── smoke_input.csv         # NEW
└── docs/
    ├── specs/2026-04-30-email-permutation-finder-design.md   # already exists
    └── plans/2026-04-30-email-permutation-finder.md          # this file
```

---

## Task 1: Repo init + test scaffolding

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo and verify Python deps**

```bash
cd "c:/Users/richa/Jolly_Claude_Code/email-permutation-finder"
git init
git add README.md LICENSE .gitignore .env.example requirements.txt docs/
git commit -m "chore: initial scaffold (README, LICENSE, requirements, spec, plan)"
pip install -r requirements.txt
```

Expected: git repo initialized, first commit made, pytest + requests + python-dotenv installed.

- [ ] **Step 2: Create `tests/conftest.py` so tests can import top-level modules**

```python
"""Shared pytest config. Adds the repo root to sys.path."""

import sys
from pathlib import Path

# Make permutation_finder.py, _permutations.py, _mv_client.py importable
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 3: Verify pytest can discover (an empty test directory)**

```bash
python -m pytest tests/ --collect-only 2>&1 | head -10
```
Expected: "no tests ran" or "collected 0 items" with no import errors.

- [ ] **Step 4: Commit conftest**

```bash
git add tests/conftest.py
git commit -m "chore(tests): add conftest with sys.path setup"
```

---

## Task 2: Name normalization

**Files:**
- Create: `_permutations.py`
- Test: `tests/test_permutations.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutations.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named '_permutations'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutations.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add _permutations.py tests/test_permutations.py
git commit -m "feat(permutations): add name normalization with umlaut + accent folding"
```

---

## Task 3: Domain normalization

**Files:**
- Modify: `_permutations.py` (add `normalize_domain`)
- Modify: `tests/test_permutations.py`

- [ ] **Step 1: Append the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutations.py -v -k normalize_domain
```
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Append implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutations.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add _permutations.py tests/test_permutations.py
git commit -m "feat(permutations): add domain normalization"
```

---

## Task 4: Pattern generation

**Files:**
- Modify: `_permutations.py` (add `generate_permutations`)
- Modify: `tests/test_permutations.py`

- [ ] **Step 1: Append the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutations.py -v -k generate_permutations
```
Expected: FAIL.

- [ ] **Step 3: Append implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutations.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add _permutations.py tests/test_permutations.py
git commit -m "feat(permutations): add top-5 pattern generator"
```

---

## Task 5: Free-email-domain blocklist

**Files:**
- Modify: `_permutations.py` (add `is_free_email_domain` + `FREE_EMAIL_DOMAINS`)
- Modify: `tests/test_permutations.py`

- [ ] **Step 1: Append the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutations.py -v -k is_free_email
```
Expected: FAIL.

- [ ] **Step 3: Append implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutations.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add _permutations.py tests/test_permutations.py
git commit -m "feat(permutations): add free-email-domain blocklist"
```

---

## Task 6: Million Verifier HTTP client

**Files:**
- Create: `_mv_client.py`
- Test: `tests/test_mv_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mv_client.py
from unittest.mock import patch, MagicMock
import pytest

import _mv_client as MV


def _mock_response(json_payload, status=200, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_payload
    r.headers = headers or {}
    r.text = str(json_payload)
    return r


def test_verify_returns_canonical_status_ok():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "ok", "email": "x@y.com"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    assert result["email"] == "x@y.com"


def test_verify_maps_catch_all_status():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "catch_all"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "catch_all"


def test_verify_maps_invalid_disposable_unknown():
    for raw in ["invalid", "disposable", "unknown"]:
        with patch("_mv_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response({"result": raw})
            result = MV.verify("x@y.com", api_key="fake")
        assert result["status"] == raw, f"failed for {raw}"


def test_verify_unknown_provider_status_maps_to_error():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "weird_new_value"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "error"


def test_verify_retries_on_timeout_then_succeeds():
    import requests as req
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.side_effect = [
            req.exceptions.Timeout("timeout"),
            _mock_response({"result": "ok"}),
        ]
        with patch("_mv_client.time.sleep"):  # don't actually sleep in tests
            result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    assert mock_get.call_count == 2


def test_verify_returns_error_after_max_retries():
    import requests as req
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.side_effect = req.exceptions.ConnectionError("boom")
        with patch("_mv_client.time.sleep"):
            result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "error"


def test_verify_aborts_on_401():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"error": "bad key"}, status=401)
        with pytest.raises(MV.MVAuthError):
            MV.verify("x@y.com", api_key="fake")


def test_verify_respects_retry_after_on_429():
    with patch("_mv_client.requests.get") as mock_get, \
         patch("_mv_client.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _mock_response({"error": "rate limited"}, status=429, headers={"Retry-After": "2"}),
            _mock_response({"result": "ok"}),
        ]
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    mock_sleep.assert_any_call(2)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_mv_client.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named '_mv_client'`.

- [ ] **Step 3: Write implementation**

```python
# _mv_client.py
"""Million Verifier HTTP client with canonical status mapping + retry logic."""

import time
import requests

API_URL = "https://api.millionverifier.com/api/v3/"
TIMEOUT = 30
MAX_RETRIES = 2

CANONICAL_STATUSES = {"ok", "catch_all", "invalid", "disposable", "unknown"}


class MVAuthError(RuntimeError):
    """Raised on HTTP 401/403 — unrecoverable, abort the run."""


def _canonicalize(raw_status: str) -> str:
    if raw_status in CANONICAL_STATUSES:
        return raw_status
    return "error"


def verify(email: str, api_key: str, mv_timeout: int = 10) -> dict:
    """Validate a single email via Million Verifier.

    Returns: {"email": str, "status": canonical_status, "raw": dict}
    Raises: MVAuthError on 401/403.
    """
    params = {"api": api_key, "email": email, "timeout": mv_timeout}
    last_exc = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, timeout=TIMEOUT)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            return {"email": email, "status": "error", "raw": {"error": str(e)}}

        if r.status_code in (401, 403):
            raise MVAuthError(f"Million Verifier rejected API key (HTTP {r.status_code}): {r.text[:200]}")

        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "5"))
            time.sleep(retry_after)
            continue  # does NOT consume a retry attempt

        if r.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            return {"email": email, "status": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        if not (200 <= r.status_code < 300):
            return {"email": email, "status": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        body = r.json()
        return {
            "email": email,
            "status": _canonicalize(body.get("result", "")),
            "raw": body,
        }

    return {"email": email, "status": "error", "raw": {"error": str(last_exc) if last_exc else "exhausted retries"}}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_mv_client.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add _mv_client.py tests/test_mv_client.py
git commit -m "feat(mv): add Million Verifier client with retry + auth-error handling"
```

---

## Task 7: Per-contact worker function

**Files:**
- Create: `permutation_finder.py` (skeleton with `process_contact`)
- Test: `tests/test_permutation_finder.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutation_finder.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
# permutation_finder.py
"""
Email Permutation Finder — top-5 name+domain patterns validated via Million Verifier.

CLI:
  python permutation_finder.py --input leads.csv --output found.csv

See docs/specs/2026-04-30-email-permutation-finder-design.md for the full design.
"""

import _permutations
import _mv_client


def process_contact(
    first_name: str,
    last_name: str,
    company_domain: str,
    mv_api_key: str,
    max_attempts: int,
) -> dict:
    """Run the permutation waterfall for one contact. Returns a result row dict."""
    if not first_name or not first_name.strip() \
            or not last_name or not last_name.strip() \
            or not company_domain or not company_domain.strip():
        return _result(verdict="skipped", error_reason="missing_field")

    if _permutations.is_free_email_domain(company_domain):
        return _result(verdict="skipped", error_reason="personal_email_domain")

    permutations = _permutations.generate_permutations(first_name, last_name, company_domain)
    if not permutations:
        return _result(verdict="skipped", error_reason="empty_after_normalization")

    permutations = permutations[:max_attempts]

    last_status = ""
    for attempt_idx, (label, candidate_email) in enumerate(permutations, start=1):
        mv = _mv_client.verify(candidate_email, api_key=mv_api_key)
        last_status = mv["status"]

        if mv["status"] == "ok":
            return _result(
                verdict="valid",
                email=candidate_email,
                permutation_used=label,
                mv_status="ok",
                mv_attempts=attempt_idx,
            )
        if mv["status"] == "catch_all":
            return _result(
                verdict="catchall_domain",
                mv_status="catch_all",
                mv_attempts=attempt_idx,
            )

    return _result(
        verdict="not_found",
        mv_status=last_status or "not_found",
        mv_attempts=len(permutations),
    )


def _result(
    verdict: str,
    email: str = "",
    permutation_used: str = "",
    mv_status: str = "",
    mv_attempts: int = 0,
    error_reason: str = "",
) -> dict:
    return {
        "email": email,
        "email_source": "permutation" if email else "",
        "permutation_used": permutation_used,
        "mv_status": mv_status,
        "mv_attempts": mv_attempts,
        "email_verdict": verdict,
        "error_reason": error_reason,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutation_finder.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add permutation_finder.py tests/test_permutation_finder.py
git commit -m "feat(finder): add per-contact processor with verdict logic"
```

---

## Task 8: JSON cache (resume-safe)

**Files:**
- Modify: `permutation_finder.py` (add cache helpers)
- Modify: `tests/test_permutation_finder.py`

- [ ] **Step 1: Append the failing test**

```python
import json
from pathlib import Path


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutation_finder.py -v -k cache
```
Expected: FAIL.

- [ ] **Step 3: Append implementation to `permutation_finder.py`**

```python
import json
from pathlib import Path


def cache_key(first_name: str, last_name: str, company_domain: str) -> str:
    """Stable cache key from normalized inputs."""
    fn = _permutations.normalize_name(first_name)
    ln = _permutations.normalize_name(last_name)
    dom = _permutations.normalize_domain(company_domain)
    return f"{fn}|{ln}|{dom}"


def load_cache(cache_path) -> dict:
    cache_path = Path(cache_path)
    if not cache_path.is_file():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache_path, cache: dict) -> None:
    """Atomic save: write to .tmp, then rename."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    tmp.replace(cache_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutation_finder.py -v -k cache
```
Expected: cache tests PASS.

- [ ] **Step 5: Commit**

```bash
git add permutation_finder.py tests/test_permutation_finder.py
git commit -m "feat(finder): add resume-safe JSON cache helpers"
```

---

## Task 9: CSV reader / writer

**Files:**
- Modify: `permutation_finder.py` (add `read_input_csv`, `write_output_csv`)
- Modify: `tests/test_permutation_finder.py`

- [ ] **Step 1: Append the failing test**

```python
import csv


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutation_finder.py -v -k csv
```
Expected: FAIL.

- [ ] **Step 3: Append implementation**

```python
import csv as _csv

REQUIRED_INPUT_COLUMNS = ("first_name", "last_name", "company_domain")
ADDED_OUTPUT_COLUMNS = (
    "email", "email_source", "permutation_used",
    "mv_status", "mv_attempts", "email_verdict", "error_reason",
)


def _normalize_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_")


def read_input_csv(path) -> list[dict]:
    """Read a CSV. Lowercases + replaces spaces in headers (e.g. 'First Name' -> 'first_name')."""
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        normalized_fieldnames = [_normalize_header(h) for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in normalized_fieldnames]
        if missing:
            raise ValueError(f"Input CSV missing required columns: {missing}")
        for raw in reader:
            normalized = {_normalize_header(k): v for k, v in raw.items()}
            rows.append(normalized)
    return rows


def write_output_csv(path, rows: list[dict]) -> None:
    """Write rows to CSV. Field order = input columns first, then added columns."""
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(",".join(REQUIRED_INPUT_COLUMNS + ADDED_OUTPUT_COLUMNS) + "\n")
        return
    all_keys: list[str] = []
    seen: set[str] = set()
    for k in REQUIRED_INPUT_COLUMNS:
        if k in rows[0]:
            all_keys.append(k); seen.add(k)
    for r in rows:
        for k in r.keys():
            if k not in seen and k not in ADDED_OUTPUT_COLUMNS:
                all_keys.append(k); seen.add(k)
    for k in ADDED_OUTPUT_COLUMNS:
        all_keys.append(k); seen.add(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutation_finder.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add permutation_finder.py tests/test_permutation_finder.py
git commit -m "feat(finder): add CSV reader (header normalization) + writer"
```

---

## Task 10: Threaded batch orchestrator

**Files:**
- Modify: `permutation_finder.py` (add `run_batch`)
- Modify: `tests/test_permutation_finder.py`

- [ ] **Step 1: Append the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutation_finder.py -v -k run_batch
```
Expected: FAIL.

- [ ] **Step 3: Append implementation**

```python
from concurrent.futures import ThreadPoolExecutor


CACHE_SAVE_EVERY = 50


def run_batch(
    contacts: list[dict],
    mv_api_key: str,
    max_attempts: int,
    cache_path,
    concurrency: int = 10,
) -> list[dict]:
    """Process all contacts. Cache hits skip MV. Returns one result row per input contact, in input order."""
    cache = load_cache(cache_path)
    results: list[dict] = [None] * len(contacts)

    to_process: list[tuple[int, dict]] = []
    for idx, c in enumerate(contacts):
        key = cache_key(c.get("first_name", ""), c.get("last_name", ""), c.get("company_domain", ""))
        if key in cache:
            results[idx] = {**c, **cache[key]}
        else:
            to_process.append((idx, c))

    def _work(item):
        idx, c = item
        out = process_contact(
            first_name=c.get("first_name", ""),
            last_name=c.get("last_name", ""),
            company_domain=c.get("company_domain", ""),
            mv_api_key=mv_api_key,
            max_attempts=max_attempts,
        )
        return idx, c, out

    completed = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for idx, c, out in ex.map(_work, to_process):
            merged = {**c, **out}
            results[idx] = merged
            cache[cache_key(c.get("first_name", ""), c.get("last_name", ""), c.get("company_domain", ""))] = out
            completed += 1
            if completed % CACHE_SAVE_EVERY == 0:
                save_cache(cache_path, cache)

    save_cache(cache_path, cache)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_permutation_finder.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add permutation_finder.py tests/test_permutation_finder.py
git commit -m "feat(finder): add threaded batch orchestrator with cache resume"
```

---

## Task 11: CLI argparse entry point

**Files:**
- Modify: `permutation_finder.py` (add `main()` + `if __name__ == "__main__"` + .env loading)
- Modify: `tests/test_permutation_finder.py`

- [ ] **Step 1: Append the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_permutation_finder.py -v -k cli
```
Expected: FAIL.

- [ ] **Step 3: Append .env loading + `main()` to `permutation_finder.py`**

Insert AT THE TOP of `permutation_finder.py` (above the existing imports):

```python
"""Email Permutation Finder — top-5 patterns + Million Verifier validation."""

import os
import sys
from pathlib import Path

# Load .env from the repo root (walking up from this file). Standard python-dotenv.
try:
    from dotenv import load_dotenv
    for _parent in Path(__file__).resolve().parents:
        if (_parent / ".env").is_file():
            load_dotenv(_parent / ".env")
            break
except ImportError:
    pass  # dotenv is optional; env vars can also come from the shell
```

Then APPEND `main()` at the bottom of the file:

```python
import argparse


def main() -> int:
    """CLI entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        description="Email permutation finder (top 5 patterns + Million Verifier).",
    )
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--cache", default=".tmp/permutation_cache.json", help="Resume cache JSON path")
    parser.add_argument("--max-attempts", type=int, default=5, help="Max MV calls per contact (1-10)")
    parser.add_argument("--concurrency", type=int, default=10, help="Parallel contacts in flight")
    parser.add_argument("--dry-run", action="store_true", help="Generate permutations only, skip MV")
    args = parser.parse_args()

    if not (1 <= args.max_attempts <= 10):
        print("ERROR: --max-attempts must be 1-10", file=sys.stderr)
        return 2

    contacts = read_input_csv(args.input)
    print(f"[input] {len(contacts)} contacts loaded from {args.input}")

    if args.dry_run:
        rows = []
        for c in contacts:
            perms = _permutations.generate_permutations(
                c.get("first_name", ""), c.get("last_name", ""), c.get("company_domain", "")
            )
            for label, email in perms[:args.max_attempts]:
                rows.append({**c, "email": email, "email_source": "permutation",
                             "permutation_used": label, "mv_status": "", "mv_attempts": 0,
                             "email_verdict": "dry_run", "error_reason": ""})
        write_output_csv(args.output, rows)
        print(f"[dry-run] wrote {len(rows)} candidate permutations to {args.output}")
        return 0

    mv_key = os.environ.get("MILLIONVERIFIER_API_KEY", "")
    if not mv_key:
        print("ERROR: MILLIONVERIFIER_API_KEY not set in environment / .env", file=sys.stderr)
        return 2

    rows = run_batch(
        contacts=contacts,
        mv_api_key=mv_key,
        max_attempts=args.max_attempts,
        cache_path=args.cache,
        concurrency=args.concurrency,
    )

    write_output_csv(args.output, rows)

    by_verdict: dict[str, int] = {}
    total_calls = 0
    for r in rows:
        by_verdict[r.get("email_verdict", "")] = by_verdict.get(r.get("email_verdict", ""), 0) + 1
        total_calls += int(r.get("mv_attempts") or 0)
    print(f"[output] wrote {len(rows)} rows to {args.output}")
    print(f"[stats] verdicts: {by_verdict}")
    print(f"[stats] total MV calls: {total_calls}  (~${total_calls * 0.0004:.4f} at $0.0004/credit)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add permutation_finder.py tests/test_permutation_finder.py
git commit -m "feat(cli): add CLI entry point with dry-run + stats"
```

---

## Task 12: End-to-end smoke fixture + dry-run check

**Files:**
- Create: `tests/fixtures/smoke_input.csv`

- [ ] **Step 1: Create smoke fixture**

Create `tests/fixtures/smoke_input.csv` with content:

```csv
first_name,last_name,company_domain
Eric,Nowinski,growthx.com
Müller,Schäfer,acme.de
Anne-Marie,Schmidt,jolly-marketer.de
Test,User,gmail.com
,Empty,emptyfirst.com
```

- [ ] **Step 2: Run the dry-run smoke test**

```bash
python permutation_finder.py \
  --input tests/fixtures/smoke_input.csv \
  --output .tmp/smoke_output.csv \
  --cache .tmp/smoke_cache.json \
  --dry-run
```

Expected stdout:
- `[input] 5 contacts loaded from tests/fixtures/smoke_input.csv`
- `[dry-run] wrote 15 candidate permutations to .tmp/smoke_output.csv`
  (3 valid contacts × 5 permutations each = 15; gmail row and empty-first row generate 0)

- [ ] **Step 3: Verify the output**

Open `.tmp/smoke_output.csv` and confirm:
- The Müller row has `mueller.schaefer@acme.de` as one permutation (umlauts normalized)
- The Anne-Marie row has `anne-marie.schmidt@jolly-marketer.de`
- The gmail.com and empty-first rows did not generate permutations (no rows for them in output)

- [ ] **Step 4: Optionally run a real test against MV** (skip to save credits)

If you want to verify the real MV path end-to-end:
1. Set `MILLIONVERIFIER_API_KEY` in `.env`.
2. Run:

```bash
python permutation_finder.py \
  --input tests/fixtures/smoke_input.csv \
  --output .tmp/smoke_live.csv \
  --cache .tmp/smoke_live_cache.json
```

Expected: ~3-15 MV calls, stdout shows verdicts grouped, cost reported under $0.01.

- [ ] **Step 5: Commit fixture**

```bash
git add tests/fixtures/smoke_input.csv
git commit -m "test(smoke): add fixture for dry-run end-to-end check"
```

---

## Task 13: Skill files at `~/.claude/skills/email-permutation-finder/`

**Files:**
- Create: `~/.claude/skills/email-permutation-finder/skill.md`
- Create: `~/.claude/skills/email-permutation-finder/references/permutation_patterns.md`

- [ ] **Step 1: Create skill folder and reference doc**

```bash
mkdir -p ~/.claude/skills/email-permutation-finder/references
```

Create `~/.claude/skills/email-permutation-finder/references/permutation_patterns.md`:

````markdown
# Permutation Patterns Reference

The tool tries these 5 patterns in this fixed order, stops on the first MV `ok`:

| # | Label | Format | Example (Eric Nowinski @ growthx.com) |
|---|-------|--------|---------------------------------------|
| 1 | `firstname.lastname` | `{first}.{last}@{domain}` | eric.nowinski@growthx.com |
| 2 | `firstname` | `{first}@{domain}` | eric@growthx.com |
| 3 | `f.lastname` | `{first[0]}.{last}@{domain}` | e.nowinski@growthx.com |
| 4 | `firstnamelastname` | `{first}{last}@{domain}` | ericnowinski@growthx.com |
| 5 | `firstname.l` | `{first}.{last[0]}@{domain}` | eric.n@growthx.com |

## Normalization

Before pattern application:
- Names: lowercase, German umlauts folded (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`), other accents stripped via NFKD, apostrophes dropped, hyphens kept.
- Domain: lowercase, strip protocol (`https://`, `http://`), strip `www.`, strip trailing path/slash.

## Free-Email Domain Blocklist

Contacts with these domains are skipped before any MV call:
`gmail.com`, `googlemail.com`, `yahoo.*`, `outlook.*`, `hotmail.*`, `live.*`, `gmx.*`, `web.de`, `t-online.de`, `aol.com`, `icloud.com`, `me.com`, `mac.com`, `proton.me`, `protonmail.com`.
````

- [ ] **Step 2: Create the skill definition**

Create `~/.claude/skills/email-permutation-finder/skill.md`:

````markdown
---
name: email-permutation-finder
description: Find B2B work emails by guessing the top 5 name+domain permutations and validating each via Million Verifier. Use when enriching contact lists with emails as a cheap "phase 0" before paid finders. Outputs verified emails, catchall-domain flags, and not-found rows. Pure CSV in / CSV out — no DB coupling. Open-source MIT tool.
---

# Email Permutation Finder

Cheapest layer of email enrichment for B2B contacts. Tries 5 common name+domain patterns and verifies each via Million Verifier. Smart-stops on Catchall domains (1 call instead of 5). Composes downstream with paid finders for the long tail.

## When to use

- Building a B2B lead list and want to skip paid-finder credits for the easy 60-70%.
- Auditing an existing email list — re-validate with smart catchall detection.
- DACH B2B specifically (pattern order tuned for it; works for any B2B but order may not be optimal).

## When NOT to use

- Personal/consumer email finding (this tool refuses gmail/gmx/etc).
- Catchall-heavy domains where you must trust patterns despite catch_all status — use a paid finder with catchall-aware verification (Findymail + Bouncepan, etc.).
- Strict-compliance pipelines where guessing email patterns is forbidden.

## Tool location

Canonical local clone:
```
c:/Users/richa/Jolly_Claude_Code/Jolly Automations/Jolly-Email-Permutation-Finder/permutation_finder.py
```

Public repo: `https://github.com/<your-org>/email-permutation-finder` (MIT).

## Quick start

```bash
# Dry run (no MV calls — verifies patterns and CSV plumbing only)
python "c:/Users/richa/Jolly_Claude_Code/Jolly Automations/Jolly-Email-Permutation-Finder/permutation_finder.py" \
  --input leads.csv \
  --output found.csv \
  --dry-run

# Real run
python "c:/Users/richa/Jolly_Claude_Code/Jolly Automations/Jolly-Email-Permutation-Finder/permutation_finder.py" \
  --input leads.csv \
  --output found.csv
```

## Input CSV

Required columns (case-insensitive headers, spaces accepted):
- `first_name`
- `last_name`
- `company_domain`

Optional columns are passed through unchanged.

## Output CSV

Input columns + these added columns:
- `email` — found email or empty
- `email_source` — `permutation` or empty
- `permutation_used` — pattern label (see `references/permutation_patterns.md`)
- `mv_status` — `ok` / `catch_all` / `invalid` / `unknown` / `error` / `not_found`
- `mv_attempts` — 1–5
- `email_verdict` — `valid` / `catchall_domain` / `not_found` / `skipped`
- `error_reason` — `missing_field` / `personal_email_domain` / empty

## Composition

Recommended pipeline:
```
list-building → email-permutation-finder → paid-finder (on rows with email_verdict != valid) → persistence
```

Each step writes a CSV; the next filters on `email_verdict`. At Jolly internally: chain with `email-enrichment-waterfall` then `jolly-lead-pool-sync`.

## Pattern reference

See `references/permutation_patterns.md` for the full pattern list, normalization rules, and free-email blocklist.

## Cost

Million Verifier ~$0.0004/credit:
- ~$0.92 per 1.000 leads in a typical DACH B2B distribution
- Compare: paid-finder-only would be ~$8 per 1.000 leads.

## Failure modes

- MV API down → run completes with `mv_status=error` for affected rows. Resume via `--cache`.
- MV auth fails (401/403) → run aborts immediately with clear error.
- Crash mid-run → cache saves every 50 lookups; rerun with the same `--cache` path resumes.

## Spec

Full design at:
```
c:/Users/richa/Jolly_Claude_Code/Jolly Automations/Jolly-Email-Permutation-Finder/docs/specs/2026-04-30-email-permutation-finder-design.md
```
````

- [ ] **Step 3: Verify the skill is discoverable**

```bash
ls ~/.claude/skills/email-permutation-finder/
```
Expected: `skill.md  references/`

```bash
head -5 ~/.claude/skills/email-permutation-finder/skill.md
```
Expected: shows the YAML frontmatter with `name` and `description`.

- [ ] **Step 4: No commit needed for skill files** (they live in `~/.claude`, not the repo).

---

## Task 14: GitHub remote setup (manual)

**Files:** none (operational)

- [ ] **Step 1: Create the GitHub repository**

User action: create a new public repository at `https://github.com/<your-org>/email-permutation-finder` with no README/LICENSE/.gitignore (to avoid conflicts with our local files).

- [ ] **Step 2: Add remote and push**

```bash
cd "c:/Users/richa/Jolly_Claude_Code/email-permutation-finder"
git remote add origin git@github.com:<your-org>/email-permutation-finder.git
git branch -M main
git push -u origin main
```

Expected: all commits pushed; GitHub shows the new repo with README rendered.

- [ ] **Step 3: Verify install instructions work for a fresh clone**

In a separate temp directory:

```bash
git clone https://github.com/<your-org>/email-permutation-finder.git /tmp/test-clone
cd /tmp/test-clone
pip install -r requirements.txt
python -m pytest tests/ -v
```

Expected: clean clone, deps install, all tests PASS.

- [ ] **Step 4: Tag v0.1.0**

```bash
cd "c:/Users/richa/Jolly_Claude_Code/email-permutation-finder"
git tag -a v0.1.0 -m "v0.1.0 - initial release"
git push origin v0.1.0
```

---

## Self-Review Checklist

After all tasks, verify:

1. **Spec coverage:**
   - Pattern generator with normalization → Tasks 2-4
   - Free-email blocklist → Task 5
   - MV client with retry + auth handling → Task 6
   - Per-contact verdict logic → Task 7
   - Cache resume → Task 8
   - CSV in/out with extra-column passthrough → Task 9
   - Threaded batch + concurrency flag → Task 10
   - CLI with all flags from spec (input, output, cache, max-attempts, concurrency, dry-run) → Task 11
   - Skill files for global discoverability → Task 13
   - GitHub distribution → Task 14

2. **Type consistency:**
   - `process_contact` returns dict with keys: `email, email_source, permutation_used, mv_status, mv_attempts, email_verdict, error_reason` — used identically in Tasks 7, 9, 10.
   - `cache_key()` signature stable between Tasks 8 and 10.
   - `_mv_client.verify()` returns `{"email", "status", "raw"}` — consumed by `process_contact` in Task 7 (reads `mv["status"]` only).

3. **No placeholders:** every step has full code or full command. No "TODO", no "fill in", no "similar to above".

4. **Composability check:** Output column `email_verdict` is the contract that downstream consumers filter on — must be exactly one of `valid / catchall_domain / not_found / skipped` (no synonyms).
