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
            try:
                retry_after = int(r.headers.get("Retry-After", "5"))
            except ValueError:
                # Retry-After may be an HTTP-date (RFC 7231) instead of delta-seconds.
                # Fall back to default rather than crashing.
                retry_after = 5
            time.sleep(retry_after)
            # 429 advances the attempt counter, so a sustained rate-limit terminates after MAX_RETRIES+1 calls (same bound as 5xx)
            continue

        if r.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            return {"email": email, "status": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        if not (200 <= r.status_code < 300):
            return {"email": email, "status": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        try:
            body = r.json()
        except ValueError as e:
            return {
                "email": email,
                "status": "error",
                "raw": {"error": f"non-json response body: {e}", "body": r.text[:200]},
            }
        return {
            "email": email,
            "status": _canonicalize(body.get("result", "")),
            "raw": body,
        }

    return {"email": email, "status": "error", "raw": {"error": str(last_exc) if last_exc else "exhausted retries"}}
