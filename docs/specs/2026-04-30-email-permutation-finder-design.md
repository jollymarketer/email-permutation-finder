# Design: Email Permutation Finder

**Date:** 2026-04-30
**Status:** Approved (design phase)
**Author:** Richard / Claude Code session

## Goal

Build a reusable, GitHub-distributable CLI tool that finds B2B work emails by guessing the most common name+domain permutations and validating each guess via Million Verifier. Pure CSV in / CSV out — no database coupling. Run as a cheap "Phase 0" before any paid finder (LeadMagic, Findymail, Prospeo). Per-lead cost target: under $0.005 in MV credits.

## Background

Cold-email pipelines today often jump straight to paid email-finder APIs (LeadMagic, Findymail, Prospeo) which charge a credit on every contact. For DACH B2B contacts where the email pattern is one of the top 5 obvious permutations (`firstname.lastname@`, `firstname@`, etc.), this is wasted spend — the email could have been guessed and verified for ~$0.0004 in MV credits instead of $0.01 in finder credits. A permutation-first layer can eliminate paid-finder calls for the 50–70% of leads where common patterns work, leaving only the long tail (catchall domains, unusual patterns) for paid finders.

This is published as a standalone open-source tool (MIT) so it can be cloned by other teams and shipped into any cold-email pipeline. Internally at Jolly, it composes downstream with `email-enrichment-waterfall` and `jolly-lead-pool-sync`.

Inspiration: Eric Nowinski's video walkthrough (Apr 27, 2026) showing a Claude-Code-built permutation guesser using Million Verifier as the cheapest filtering layer.

## Non-Goals

- Paid-finder fallback inside this tool (Prospeo, Blitz, LeadMagic, Findymail). Each user/team chains their own paid finder downstream; this tool stays single-purpose.
- Persistence into any database (Supabase, Postgres, etc.). Output is CSV. Persistence is the consumer's job.
- Trigger.dev cloud deployment / hosted runs. Local CLI only.
- Multi-provider verification waterfall (NeverBounce as second opinion). Million Verifier is the only verifier in this tool.
- Pattern auto-tuning based on hit rates. Default order is fixed; a future tuning loop is out of scope.

## Architecture

Standalone CLI, distributed via GitHub clone:

```text
input.csv (first_name, last_name, company_domain)
            │
            ▼
permutation_finder.py
  ├─ normalize names + domain (umlauts → ASCII, lowercase)
  ├─ filter free-email-domain blocklist
  ├─ generate top 5 permutations in fixed order
  ├─ threaded batch (10 contacts at a time)
  │    └─ per contact, sequential MV calls until:
  │         • status="ok"        → valid, stop
  │         • status="catch_all" → catchall_domain, stop
  │         • 5 attempts exhausted → not_found
  └─ write enriched CSV
            │
            ▼
output.csv (input cols + email, email_source, permutation_used,
            mv_status, mv_attempts, email_verdict, error_reason)
```

## Repository Layout

```text
email-permutation-finder/
├── README.md                   # Client-facing English docs
├── LICENSE                     # MIT
├── .gitignore                  # ignores .env, .tmp/, caches
├── .env.example                # MILLIONVERIFIER_API_KEY only
├── requirements.txt            # requests, python-dotenv, pytest
├── permutation_finder.py       # CLI entry point
├── _permutations.py            # Pure pattern + normalization
├── _mv_client.py               # Million Verifier HTTP client + retry
├── tests/
│   ├── conftest.py             # sys.path setup so tests can import top-level modules
│   ├── test_permutations.py
│   ├── test_mv_client.py
│   ├── test_permutation_finder.py
│   └── fixtures/
│       └── smoke_input.csv
└── docs/
    ├── specs/
    │   └── 2026-04-30-email-permutation-finder-design.md
    └── plans/
        └── 2026-04-30-email-permutation-finder.md
```

Local clone path: `c:/Users/richa/Jolly_Claude_Code/email-permutation-finder/`

## Components

### 1. Pattern Generator (`_permutations.py`)

Pure function module, no I/O. Testable in isolation.

```python
def normalize_name(name: str) -> str:
    """Lowercase, replace umlauts (ä→ae, ö→oe, ü→ue, ß→ss, é→e, etc.)"""

def normalize_domain(domain: str) -> str:
    """Lowercase, strip http(s)://, strip www., strip trailing slash"""

def generate_permutations(first_name: str, last_name: str, domain: str) -> list[tuple[str, str]]:
    """Returns ordered list of (pattern_label, email) tuples.

    Top 5 patterns:
      1. firstname.lastname@domain
      2. firstname@domain
      3. f.lastname@domain
      4. firstnamelastname@domain
      5. firstname.l@domain

    Pattern labels are stable identifiers used in the permutation_used output
    column — do not change them without bumping a major version.
    """

def is_free_email_domain(domain: str) -> bool:
    """True if domain is a known consumer free-email provider."""
```

### 2. Million Verifier Client (`_mv_client.py`)

- Endpoint: `https://api.millionverifier.com/api/v3/?api=<key>&email=<email>&timeout=10`
- 30s HTTP timeout
- Retry policy:
  - Timeout / ConnectionError: 1 retry, 2s backoff
  - HTTP 429: read `Retry-After` header, sleep, retry (does not consume an attempt)
  - HTTP 5xx: 2 retries with exponential backoff (2s, 4s)
  - HTTP 401/403 (bad API key): abort the entire run via `MVAuthError`
- Returns: dict with `email`, `status` (canonical: `ok`, `catch_all`, `invalid`, `disposable`, `unknown`, `error`), `raw` (provider response)

### 3. Per-Contact Worker (in `permutation_finder.py`)

Pure function called from a thread pool. For each contact:

1. Pre-check:
   - Required fields present and non-empty (`first_name`, `last_name`, `company_domain`)? If not → `verdict=skipped`, `error_reason=missing_field`.
   - Domain in free-email blocklist? → `verdict=skipped`, `error_reason=personal_email_domain`.
2. Generate top-5 permutations.
3. For each permutation in order, sequentially:
   - Call MV. Branch on result:
     - `ok` → record `(email, permutation_used, mv_status='ok', mv_attempts=N, verdict='valid')`, stop.
     - `catch_all` → record `(email='', mv_status='catch_all', mv_attempts=1, verdict='catchall_domain')`, stop.
     - `invalid` / `disposable` / `unknown` → continue to next permutation.
     - `error` after retries exhausted → continue to next permutation; track in `mv_status='error'` only if all 5 fail.
4. If 5 attempts produce no `ok` and no `catch_all`: `verdict=not_found`, `mv_attempts=5`. If all 5 attempts returned `error` after retries, the final row is still `verdict=not_found` but `mv_status=error` so cost-tracking can distinguish "domain genuinely has no findable pattern" from "MV API was unreliable for this contact".

### 4. Cache (`.tmp/permutation_cache.json` by default)

JSON file keyed by `f"{normalized_first}|{normalized_last}|{normalized_domain}"`. Each value is the full result row dict. On run start: load cache, skip cached contacts. On run progress: save every 50 lookups + on SIGINT (Ctrl-C) handler. Delete the file to force a fresh run.

### 5. Output Writer (in `permutation_finder.py`)

CSV writer that preserves all input columns + appends:

| Column | Type | Values |
|--------|------|--------|
| `email` | str / empty | Found email, lowercase normalized |
| `email_source` | str / empty | `permutation` (constant for this tool) |
| `permutation_used` | str / empty | Pattern label (e.g. `firstname.lastname`) |
| `mv_status` | str | `ok` / `catch_all` / `invalid` / `unknown` / `error` / `not_found` |
| `mv_attempts` | int | 1–5 |
| `email_verdict` | str | `valid` / `catchall_domain` / `not_found` / `skipped` |
| `error_reason` | str / empty | `missing_field` / `personal_email_domain` / empty |

## CLI

```bash
python permutation_finder.py \
  --input <path>.csv \
  --output <path>.csv \
  [--cache .tmp/permutation_cache.json] \
  [--max-attempts 5] \
  [--concurrency 10] \
  [--dry-run]
```

| Flag | Default | Required | Purpose |
|------|---------|----------|---------|
| `--input` | — | yes | CSV path with `first_name`, `last_name`, `company_domain` |
| `--output` | — | yes | CSV path for enriched output |
| `--cache` | `.tmp/permutation_cache.json` | no | Resume cache file path |
| `--max-attempts` | 5 | no | Cap on MV calls per contact (1–10) |
| `--concurrency` | 10 | no | Parallel contacts in flight |
| `--dry-run` | off | no | Generate permutations only, skip MV calls |

## Configuration

### Environment Variables (read from `.env` in the repo root)

```
MILLIONVERIFIER_API_KEY=    # required (unless --dry-run)
```

`.env` loading uses a walking-up search from `permutation_finder.py` so the tool works regardless of where it's run from. `python-dotenv` is the standard library used.

### Free-Email-Domain Blocklist (in-code constant in `_permutations.py`)

`gmail.com`, `googlemail.com`, `yahoo.com`, `yahoo.de`, `yahoo.co.uk`, `yahoo.fr`, `outlook.com`, `outlook.de`, `hotmail.com`, `hotmail.de`, `hotmail.fr`, `live.com`, `live.de`, `gmx.de`, `gmx.net`, `gmx.com`, `gmx.at`, `gmx.ch`, `web.de`, `t-online.de`, `aol.com`, `icloud.com`, `me.com`, `mac.com`, `proton.me`, `protonmail.com`.

## Cost Model

Million Verifier pricing: ~$0.0004 per credit at typical volumes.

Per-lead cost (1.000-lead run, realistic distribution for DACH B2B):

| Bucket | Share | MV calls/lead | Calls | Cost |
|--------|-------|---------------|-------|------|
| Hit on pattern 1–2 | 50% | 2 (avg) | 1.000 | $0.40 |
| Catchall domain (smart-stop) | 30% | 1 | 300 | $0.12 |
| Not findable in top 5 | 20% | 5 | 1.000 | $0.40 |
| **Total** | 100% | — | **2.300** | **~$0.92** |

Comparison: same 1.000 leads through a paid finder like LeadMagic alone (~80% hit rate at ~$0.01/find) would cost ~$8 in finder credits. Permutation-first reduces total spend significantly when chained with a paid finder downstream: only the ~30% catchall + ~20% not-found leads pass through.

## Composition

This tool is a building block. Recommended pipeline for cold-email outbound:

1. **List building** — produces raw lead list with `first_name`, `last_name`, `company_domain`.
2. **email-permutation-finder** (this tool) — finds easy emails cheaply.
3. **Paid email finder** (LeadMagic / Findymail / Prospeo / etc.) — runs on rows where `email_verdict != valid`.
4. **Persistence step** — caller's choice (Supabase, Postgres, in-house CRM, etc.).

Each step is independently runnable. No coupling between this tool and the persistence layer.

## Distribution

- **Repository:** `https://github.com/<your-org>/email-permutation-finder` (public, MIT)
- **Install:** `git clone … && pip install -r requirements.txt`
- **No PyPI release** for v1 — clone-and-run is sufficient for the target audience (small ops/SDR teams).

## Testing

- Unit tests for `_permutations.py`: pattern generation, umlaut normalization, domain normalization, edge cases (empty names, single-character names, hyphenated names, names with apostrophes), free-email blocklist.
- Unit tests for `_mv_client.py`: canonical status mapping, retry behavior, 401/403 abort, 429 retry-after handling — all with mocked `requests`.
- Unit tests for `permutation_finder.py`: per-contact worker verdict logic, cache load/save, CSV reader/writer with header normalization, threaded batch with cache resume, CLI entry point including dry-run.
- Manual end-to-end smoke test on a 5-row CSV fixture covering hits, catchall, not-found, free-email skip, and missing-field skip.

## Open Questions

None at design close. All architectural decisions (standalone vs. integrated, attempt cap, catchall handling, persistence policy, distribution model, license) were resolved during brainstorming on 2026-04-30.

## Out of Scope (Future Work)

- Pattern A/B tuning based on observed hit rates per domain segment.
- Cloud deployment via Trigger.dev / Lambda / similar.
- Pattern set 6–10 (the long tail) re-enabled as `--max-attempts 10` for users who want maximum coverage and accept the higher cost.
- Per-domain pattern memory: if domain X consistently uses pattern Y, skip patterns 1, 2, 3 next time and try Y first. Requires a domain → pattern mapping cache.
- PyPI release with `pip install email-permutation-finder` and a `permutation-finder` console script.
- Alternative verifier backends (NeverBounce, ZeroBounce) behind a `--verifier` flag.
