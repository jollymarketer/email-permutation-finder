# permutation_finder.py
"""
Email Permutation Finder — top-5 name+domain patterns validated via Million Verifier.

CLI:
  python permutation_finder.py --input leads.csv --output found.csv

See docs/specs/2026-04-30-email-permutation-finder-design.md for the full design.
"""

import os

# Load .env from the repo root (walking up from this file). Standard python-dotenv.
try:
    from pathlib import Path as _Path
    from dotenv import load_dotenv
    for _parent in _Path(__file__).resolve().parents:
        if (_parent / ".env").is_file():
            load_dotenv(_parent / ".env")
            break
except ImportError:
    pass  # dotenv is optional; env vars can also come from the shell

import argparse
import csv as _csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _permutations
import _mv_client


REQUIRED_INPUT_COLUMNS = ("first_name", "last_name", "company_domain")
ADDED_OUTPUT_COLUMNS = (
    "email", "email_source", "permutation_used",
    "mv_status", "mv_attempts", "email_verdict", "error_reason",
)


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
        mv_status=last_status,
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


CACHE_SAVE_EVERY = 50


def run_batch(
    contacts: list[dict],
    mv_api_key: str,
    max_attempts: int,
    cache_path,
    concurrency: int = 10,
) -> list[dict]:
    """Process all contacts. Cache hits skip MV. Returns one result row per input contact, in input order.

    Cache writes happen ONLY in this coordinator function (single-writer pattern) — workers never touch
    the cache directly. This avoids lost-update races without needing a lock.

    Worker exceptions are caught per-row: if process_contact raises, the row is recorded with
    email_verdict="error" and error_reason="worker_exception: <Type>: <message>", and the batch
    continues. This prevents one bad row from killing all unsaved progress since the last cache
    checkpoint. Note: this means email_verdict has 5 possible values (valid, catchall_domain,
    not_found, skipped, error).
    """
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
        try:
            out = process_contact(
                first_name=c.get("first_name", ""),
                last_name=c.get("last_name", ""),
                company_domain=c.get("company_domain", ""),
                mv_api_key=mv_api_key,
                max_attempts=max_attempts,
            )
        except Exception as e:
            out = _result(
                verdict="error",
                error_reason=f"worker_exception: {type(e).__name__}: {e}",
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
