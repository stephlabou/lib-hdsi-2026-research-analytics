# lib-hdsi-2026-research-analytics
Repository for research analytics project for 2026 HDSI Undergraduate Research Scholarship

## OpenAlex UCSD extraction

Pulls raw OpenAlex records (works, 2020-2026) affiliated with UC San Diego and its
related organizations directly from OpenAlex's public S3 snapshot
(`s3://openalex/data/parquet/`) using DuckDB's `httpfs` extension. This bucket is
anonymous/public under the AWS Open Data program, so **no AWS account or credentials
are needed**.

### Setup

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it.
2. Place the organizational identifiers spreadsheet at the **repo root**, named exactly:
   ```
   Bibliometrics - Organizational identifiers.xlsx
   ```
   `src/openalex_ucsd/config.py` reads this file directly (`Sheet1`) and includes every
   organization whose "Query inclusion" column is not `no`. To change which
   organizations are included, edit that sheet rather than the code.
3. Install dependencies:
   ```
   uv sync
   ```

### Running the extraction

```
uv run python -m openalex_ucsd.extract --limit-files N
```

- Output lands in `data/raw/works/`, one gzipped JSON Lines file per source snapshot
  partition, preserving the raw OpenAlex record structure as-is.
- The job is **resumable at the file level**: each processed source partition gets a
  `.done` marker, so re-running the same command skips everything already done and
  continues where it left off. Safe to stop and restart at any time.
- Omit `--limit-files` to process everything remaining; pass it to cap how many
  *not-yet-done* manifest files get processed in one run.
- `--row-limit N` caps rows read per source file — useful only for quickly testing
  changes, not for real extraction.

### How big is this, and how many files should I run at once?

The `works` entity snapshot is currently **1898 partition files, ~744GB total,
~464M records**, partitioned by `updated_date` rather than by publication year or
institution — so every partition has to be scanned regardless of date range, and
there's no cheap way to skip most of them. Per-file time varies hugely: tiny early
partitions finish in under a second, while the large recent ones (hundreds of MB,
300k+ rows) take **30-40 seconds each**, almost all of it spent evaluating the nested
`authorships[].institutions[].ror` filter.

Recommendations:
- **Run in batches of 10 files max**, not the full 1898 at once. Each `uv run` process
  currently holds one long-lived DuckDB connection for the whole batch, and its memory
  footprint grows over the run — a 160-file batch was observed climbing to ~10GB RSS.
  Keeping batches to 10 files, and checking `free -h` between batches, avoids pushing
  the machine towards OOM. (A fix to recycle the connection periodically and cap
  `memory_limit` is planned — once that's in, larger batches should be safe.)
- Expect a full run across all ~1898 files to take **on the order of many hours**
  cumulatively (tens of hours of actual scan time), given the per-file costs above —
  plan to run it across multiple sessions rather than in one sitting.
- If a batch run gets interrupted or killed, nothing is lost — just re-run the same
  command; already-done files are skipped automatically.
