# _bb_client.py
"""BounceBan HTTP client (sync) for catchall-domain fallback validation.

Used by permutation_finder.process_contact() when Million Verifier returns
catch_all on a candidate. BounceBan's DeepVerify can distinguish deliverable
catch-alls from risky ones, so we switch the validator (not the candidate set)
and re-run remaining permutations through BB instead of MV.

Returns canonical results: deliverable | risky | undeliverable | unknown | error.
"""

import time
import requests

API_URL = "https://api-waterfall.bounceban.com/v1/verify/single"
TIMEOUT_SECONDS = 120
MAX_RETRIES = 2

CANONICAL_RESULTS = {"deliverable", "risky", "undeliverable", "unknown"}


class BBAuthError(RuntimeError):
    """Raised on HTTP 401/403 — unrecoverable, abort the run."""


def _canonicalize(raw_result: str) -> str:
    if raw_result in CANONICAL_RESULTS:
        return raw_result
    return "error"


def verify(email: str, api_key: str) -> dict:
    """Validate a single email via BounceBan DeepVerify mode.

    Returns: {"email": str, "result": canonical, "raw": dict}
    Raises: BBAuthError on 401/403 (auth / insufficient credits).
    """
    params = {"email": email, "mode": "deepverify", "timeout": str(TIMEOUT_SECONDS)}
    headers = {"Authorization": api_key}
    last_exc = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=TIMEOUT_SECONDS + 30)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            return {"email": email, "result": "error", "raw": {"error": str(e)}}

        if r.status_code in (401, 403):
            raise BBAuthError(f"BounceBan rejected API key / no credits (HTTP {r.status_code}): {r.text[:200]}")

        if r.status_code == 429:
            try:
                retry_after = int(r.headers.get("Retry-After", "5"))
            except ValueError:
                retry_after = 5
            time.sleep(retry_after)
            continue

        if r.status_code == 408:
            return {"email": email, "result": "unknown", "raw": {"error": "timeout"}}

        if r.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            return {"email": email, "result": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        if not (200 <= r.status_code < 300):
            return {"email": email, "result": "error", "raw": {"http_status": r.status_code, "body": r.text[:200]}}

        try:
            body = r.json()
        except ValueError as e:
            return {
                "email": email,
                "result": "error",
                "raw": {"error": f"non-json response body: {e}", "body": r.text[:200]},
            }
        return {
            "email": email,
            "result": _canonicalize(body.get("result", "")),
            "raw": body,
        }

    return {"email": email, "result": "error", "raw": {"error": str(last_exc) if last_exc else "exhausted retries"}}
