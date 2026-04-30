# permutation_finder.py
"""
Email Permutation Finder — top-5 name+domain patterns validated via Million Verifier.

CLI:
  python permutation_finder.py --input leads.csv --output found.csv

See docs/specs/2026-04-30-email-permutation-finder-design.md for the full design.
"""

import json
from pathlib import Path

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
