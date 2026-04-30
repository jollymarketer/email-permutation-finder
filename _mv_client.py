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
