# email-permutation-finder

Cheap, fast B2B work-email finder. Guesses the top 5 most common name+domain permutations and validates each via [Million Verifier](https://www.millionverifier.com/). Smart-stops on catch-all domains.

Designed as the cheap "phase 0" before paid email-finder APIs (LeadMagic, Findymail, Prospeo, etc.). Typical cost: **~$1 per 1.000 leads**.

## How it works

For each contact (`first_name`, `last_name`, `company_domain`), generate up to 5 patterns in fixed order:

| # | Label | Format |
|---|-------|--------|
| 1 | `firstname.lastname` | `eric.nowinski@growthx.com` |
| 2 | `firstname` | `eric@growthx.com` |
| 3 | `f.lastname` | `e.nowinski@growthx.com` |
| 4 | `firstnamelastname` | `ericnowinski@growthx.com` |
| 5 | `firstname.l` | `eric.n@growthx.com` |

For each candidate, call Million Verifier:
- `ok` → done, mark valid
- `catch_all` → done, mark catchall (don't trust, don't try more patterns on the same domain)
- `invalid` / `disposable` / `unknown` → try the next pattern
- After 5 attempts without `ok` → mark `not_found`

Free-email domains (Gmail, GMX, Outlook, etc.) are skipped without any API call. Names are normalized first (German umlauts, accents, hyphens, apostrophes).

## Install

```bash
git clone https://github.com/<your-org>/email-permutation-finder.git
cd email-permutation-finder
pip install -r requirements.txt
cp .env.example .env
# edit .env, set MILLIONVERIFIER_API_KEY
```

## Usage

```bash
# Dry run (no API calls — verifies CSV plumbing only)
python permutation_finder.py --input leads.csv --output found.csv --dry-run

# Real run
python permutation_finder.py --input leads.csv --output found.csv
```

### Input CSV

Required columns (case-insensitive headers):
- `first_name`
- `last_name`
- `company_domain`

Extra columns (`linkedin_url`, `company_name`, etc.) are passed through to the output unchanged.

### Output CSV

Input columns + these:

| Column | Values |
|--------|--------|
| `email` | found email or empty |
| `email_source` | `permutation` or empty |
| `permutation_used` | pattern label (`firstname.lastname`, etc.) |
| `mv_status` | `ok` / `catch_all` / `invalid` / `unknown` / `error` / `not_found` |
| `mv_attempts` | 1–5 |
| `email_verdict` | `valid` / `catchall_domain` / `not_found` / `skipped` / `error` |
| `error_reason` | `missing_field` / `personal_email_domain` / empty |

## CLI flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--input` | required | Input CSV |
| `--output` | required | Output CSV |
| `--cache` | `.tmp/permutation_cache.json` | Resume cache. Delete to start fresh. |
| `--max-attempts` | `5` | Cap on patterns tried per contact (1–10) |
| `--concurrency` | `10` | Parallel contacts in flight |
| `--dry-run` | off | Generate permutations only, skip MV calls |

## Cost

Million Verifier ~$0.0004 per credit. For a typical 1.000-lead DACH B2B run:

| Bucket | Share | Calls/lead | Total calls | Cost |
|--------|-------|------------|-------------|------|
| Hits on pattern 1–2 | 50% | 2 | 1.000 | $0.40 |
| Catch-all domain (smart-stop) | 30% | 1 | 300 | $0.12 |
| Not findable | 20% | 5 | 1.000 | $0.40 |
| **Total** | | | **2.300** | **~$0.92** |

## Resume

If a run crashes or you Ctrl-C it, just rerun with the same `--cache` path. Already-processed contacts are skipped.

## Composition

This tool only does permutation guessing. For the long tail (catchall domains, unusual patterns), chain a paid email finder afterward (Findymail handles catchall via Bouncepan; LeadMagic, Prospeo, etc. for unusual patterns).

## License

MIT — see [LICENSE](LICENSE).
