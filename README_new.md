# OpenAlex via the Command Line Interface (CLI)

This branch documents the command line interface approach for pulling UC San Diego content from OpenAlex (workflow part 1), converting it to tabular format (workflow part 2), and running basic exploratory analysis (workflow part 3).

## What does this approach do?

Uses the official OpenAlex CLI (`openalex download`) to download the complete metadata record for every work affiliated with UCSD and related organizations from 2020 to 2026. The CLI writes one JSON file per work. A second script flattens those files into CSV tables, and a third produces summary statistics, tables and charts.

CLI docs: https://help.openalex.org/access/cli/

## Pipeline

| Step | Script | Output |
| --- | --- | --- |
| 0 | `config.py` | Settings: ROR IDs, years, folders. The only file you should need to edit. |
| 1 | `01_download.py` | `data/full/raw_json/W*.json`, one JSON file per work |
| 2 | `02_flatten.py` | `data/full/tables/`: `works.csv`, `authorships.csv`, `topics.csv`, `funders.csv`, `citations_by_year.csv` |
| 3 | `03_analysis.py` | `data/full/figures/`: `summary.txt`, summary CSV tables, 4 PNG charts |

Test helper: `tests/make_sample_data.py` makes 400 fake works so steps 2 and 3 can be tried without downloading anything.

## The query

**Date run:** 2026-11-04

**Organizations (ROR IDs, from the organizational identifiers spreadsheet):**

| Organization | ROR |
| --- | --- |
| University of California San Diego | 0168r3w48 |
| San Diego Supercomputer Center | 04mg3nk07 |
| Scripps Institution of Oceanography | 04v7hvq31 |
| University of California San Diego Medical Center | 03aw5sn18 |

**Time range:** 2020 - 2026

**Exact filter** (built by `01_download.py`; `|` means OR):

```
authorships.institutions.ror:https://ror.org/0168r3w48|https://ror.org/04mg3nk07|https://ror.org/04v7hvq31|https://ror.org/03aw5sn18,publication_year:2020-2026
```

A work is returned if at least one author is affiliated with any of the four organizations. The filter matches those organizations exactly. It does not automatically include other child organizations (for example UC San Diego Health System) that are not in the spreadsheet's "yes" list.

## Setup

1. Install the tools:
   ```
   pip install openalex-official pandas matplotlib networkx
   ```
2. Get a free API key at openalex.org and set it:
   ```
   export OPENALEX_API_KEY="your-key"
   ```
   (Windows PowerShell: `$env:OPENALEX_API_KEY="your-key"`)
3. Check the key and credits: `openalex status --api-key $OPENALEX_API_KEY`
4. ROR IDs and years are set in `config.py`. To leave an organization out, delete its line there.

## Running the workflow

```
python 01_download.py --count-only                    # how many works match? (one cheap request)
OPENALEX_RUN=test python 01_download.py --test        # one week of data first
python 01_download.py                                 # full download
python 02_flatten.py                                  # JSON -> CSV tables
python 03_analysis.py                                 # stats, tables, charts
```

- `--dry-run` prints the command without running it.
- `OPENALEX_RUN=test` keeps a trial run in `data/test/`, separate from `data/full/`.
- The CLI checkpoints its progress. If the download stops, run the same command again to resume.
- Every script prints its own size report.

## How big is this?

**Compare against:** the OQL web interface returned about 135,600 works for the same organizations and years on 2026-11-03. The CLI count one day later was about 3% lower (see Limitations).

The full download **did not finish**: it stopped when the disk filled up. The numbers below describe the partial download.

| Measure | Result |
| --- | --- |
| Works matched (`--count-only`) | 131,290 |
| JSON files downloaded before the run stopped | 60,536 (about 46% of the works) |
| Raw JSON size of those files | 4,100,095,268 bytes (about 3.8 GB) |
| Average size per work | about 66 KB |
| Estimated size of the complete download | about 8.9 GB (131,290 works x 66 KB; an extrapolation, not a measurement) |
| Download time | about 17-18 minutes before stopping (the resumed run lasted about 15.5 minutes) |
| Download speed | about 1.7-2.2 MB/s on this connection |
| CSV tables total size (after step 2) | not completed |

**Storage:** the CLI keeps one JSON file per work, so a full run creates about 131,000 files, each holding the complete record (full author list, locations, referenced works). The run stopped with `[Errno 28] No space left on device` (recorded in `openalex-download.log` in the output folder). The log also shows several 504 Gateway Timeout and connection-timeout warnings from OpenAlex before the failure. The checkpoint let the download resume after those errors. Many small files also use more disk than their raw size suggests, and they are slow to copy, zip or share.

Suggested ways to reduce storage (not yet implemented in the scripts):
- Download one year at a time, flatten it to CSV, then delete that year's raw JSON.
- Point `--output` to an external drive, or run on a cloud machine. The CLI also supports an S3 option.
- Compress or delete the raw JSON once the CSV tables exist.

## Results

Not completed on real data. The full download stopped at 60,536 of 131,290 works, so steps 2 and 3 were not run on the full data set. Running them on a partial download would give misleading totals.

When the full run is finished, the outputs will be in `data/full/figures/`:

- Total works 2020-2026 and in the last 5 years (2022-2026), and unique UCSD author IDs: `summary.txt`
- Journal-article citations by year and per unique researcher: `citations_by_year.csv`
- Top 10 publishers with top 5 journals: `top_publishers_journals.csv`
- Top 10 funders with top 5 topic areas: `top_funders_topics.csv`
- Charts: `fig_formats_by_year.png`, `fig_open_access.png`, `fig_collab_countries.png`, `fig_collab_network.png`

## How the CLI compares to the other approaches

| | Web / OQL | API | CLI | Snapshot |
| --- | --- | --- | --- | --- |
| Effort | Point and click | Write your own paging code | One command | Large download, own filtering |
| Output | Browser export | JSON you collect yourself | One JSON file per work | The whole database |
| Paging, retries, resume | Handled by the browser | You write it | Built in | Not applicable |
| Entity types | Several | All | Works only (currently) | All |
| Scriptable and repeatable | Manual steps | Yes | Yes | Yes |
| Needs local storage | No | Yes | Yes (heaviest part) | Yes |

## Limitations

**The CLI itself** (per the OpenAlex docs and the PyPI page, v0.3.x, November 2026; re-check with `openalex --help`)
- Works only. There is no command for authors, institutions or funders (listed as planned). The task of matching faculty and staff to OpenAlex author IDs therefore needs the REST API in a separate script.
- No CSV export, which is why `02_flatten.py` exists.
- Needs an API key, even for metadata.
- Described as a work in progress, so options may change.
- Extra files (`openalex-download.log`, a checkpoint file) appear in the output folder. The scripts ignore them.

**The data and our choices**
- OpenAlex keeps only the first 100 authors per work (`is_authors_truncated`), so papers with very large author lists undercount UCSD researchers. Step 3 reports how many works are affected.
- Funder coverage is partial. Many works list no funder. The old `grants` field was removed, so funding comes from `funders`.
- Author IDs are algorithmic profiles. One person may be split across several IDs, or merged with someone else.
- 2026 is a partial year, and counts change whenever OpenAlex updates. Record the date of each run.
- The CLI count (131,290 on 2026-11-04) is about 3% below the OQL count (about 135,600 on 2026-11-03). Possible causes, not yet checked: the one-day gap, or OQL selecting by institution ID while the CLI filter matches ROR IDs.

**Testing status**
- `--count-only` ran against the live API.
- A test run completed through all three steps (download, flatten, analysis).
- The full download ran for about 17-18 minutes and stopped at 60,536 files when the disk filled up. Steps 2 and 3 have not been run on the full data.

## Definitions used in the analysis (to confirm)

- **Last 5 years:** 2022-2026, reported alongside the full 2020-2026 total.
- **Journal article:** work type `article` in a source of type `journal`.
- **Books:** work types `book` and `book-chapter`.
- **Citation metric:** lifetime citations (`cited_by_count`) of journal articles, grouped by publication year, divided by the unique UCSD authors on those articles. An alternative is citations received in each year (`citations_by_year.csv`, step 2).
- **UCSD researcher:** a distinct OpenAlex author ID on an authorship at one of the four ROR IDs.
- **Funder topic areas:** OpenAlex has only 4 domains, so `FUNDER_TOPIC_LEVEL` in `config.py` defaults to the 26 fields.
- **Collaboration charts:** the US is excluded by default (`INCLUDE_US_IN_COLLAB_CHART` in `config.py`).
