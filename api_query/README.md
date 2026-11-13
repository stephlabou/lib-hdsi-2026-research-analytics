# OpenAlex via the API

This folder holds the API approach for pulling UC San Diego content from
OpenAlex (workflow part 1) and converting it to tabular format (workflow
part 2).

## What does this approach do?

Python scripts send requests straight to the OpenAlex API
(`https://api.openalex.org/works`), page through every UCSD-affiliated work
from 2020 to 2026, save the raw results, and flatten them into CSV tables.

API docs: https://docs.openalex.org/how-to-use-the-api/api-overview

| File | What it does |
| --- | --- |
| `config.py` | The organizations, years, and filter. Edit here to change the scope. |
| `fetch_works.py` | Step 1: downloads every matching work to one gzipped file. |
| `to_tables.py` | Step 2: turns that file into four CSV tables. |
| `check_tables.py` | Step 3: checks the tables against OpenAlex. |

## The query

**Organizations (OpenAlex institution IDs):** same four as the OQL approach.

| Organization | OpenAlex ID |
| --- | --- |
| University of California San Diego | I36258959 |
| San Diego Supercomputer Center | I181653535 |
| Scripps Institution of Oceanography | I150209017 |
| University of California San Diego Medical Center | I4210132395 |

**Time range:** 2020 - 2026

**Exact API query** (paste into a browser to see the first 25 results):

```
https://api.openalex.org/works?filter=authorships.institutions.id:I36258959|I181653535|I150209017|I4210132395,publication_year:2020-2026
```

In the filter, `|` means OR and `,` means AND. So this reads: works from any
of the four organizations AND published 2020-2026. Add
`&group_by=publication_year` or `&group_by=type` to get counts instead of
records.

## How to run

All commands run from the repository's top folder.

**Setup.** You need a free API key. Without one, OpenAlex returns only the
first page of results.

```bash
pip install -r requirements.txt
export OPENALEX_API_KEY=...   # free key at https://openalex.org/settings/api
```

**1. Download** (about 1,300 requests, about $0.13 of the free $1/day):

```bash
python api_query/fetch_works.py
```

Saves to `data/raw/ucsd_works.jsonl.gz`. To test without a key, add
`--out data/raw/sample.jsonl.gz --max-pages 1` (first 100 works only).

**2. Convert to tables:**

```bash
python api_query/to_tables.py data/raw/ucsd_works.jsonl.gz --out-dir data/tables
```

| Table | One row per | Key columns |
| --- | --- | --- |
| `works.csv` | work | year, type, citations, FWCI, OA status, journal, publisher, primary topic → domain, # UCSD authors |
| `authorships.csv` | work × author × institution | author order, author ID, ORCID, institution, ROR, country, `is_ucsd_affiliation` |
| `funders.csv` | work × funder | funder ID, name, ROR |
| `topics.csv` | work × topic | topic, subfield, field, domain, score |

All tables join on `work_id`. IDs are shortened (`W123…`, `A123…`).

**3. Check accuracy:**

```bash
python api_query/check_tables.py --tables data/tables --sample 25
```

- **Year totals:** compares works per year in `works.csv` with OpenAlex's own
  count. Only meaningful after a full download.
- **Spot check:** looks up random works in OpenAlex again and compares every
  field, plus the number of authors in `authorships.csv`. FWCI and citation
  counts that changed are reported separately, not as errors.

**Tested (2026-11-09)** on a 100-work download without a key: all 25
spot-checked works matched, and every work had at least one UCSD author. The
full download hasn't been run yet because it needs a key.

## Results

**Total works:** 131,290 on 2026-11-09 (131,440 on 2026-11-04).

**Works per year:**

| Year | 2026-11-04 | 2026-11-09 |
| --- | --- | --- |
| 2020 | 20,187 | 20,368 |
| 2021 | 17,763 | 17,972 |
| 2022 | 17,285 | 17,564 |
| 2023 | 17,744 | 18,040 |
| 2024 | 17,744 | 17,982 |
| 2025 | 17,855 | 18,397 |
| 2026 (partial) | 22,862 | 20,967 |

**Works per type, top 10** (2026-11-04):

| Type | Works |
| --- | --- |
| article | 67,932 |
| dataset | 21,840 |
| preprint | 7,664 |
| conference-paper | 7,008 |
| conference-abstract | 6,152 |
| review | 6,027 |
| other | 5,772 |
| book-chapter | 3,191 |
| editorial | 1,630 |
| erratum | 854 |

**Each organization alone** (2026-11-04):

| Organization | Works |
| --- | --- |
| University of California San Diego | 129,711 |
| San Diego Supercomputer Center | 733 |
| Scripps Institution of Oceanography | 8,551 |
| UC San Diego Medical Center | 644 |

These sum to 139,639, compared with 131,440 combined, so about 8,200 works
are affiliated with more than one of the four organizations.

## Usability notes

- **Size.** In a random sample of 100 works, records averaged **26 KB of
  JSON** each (median 22 KB). For 131,290 works, that's about **3.5 GB
  uncompressed**, or roughly **0.4–0.6 GB** as the gzipped file the script
  writes. Most of it is fields we don't use (references, related works,
  abstracts). A few huge collaborations are much bigger: one work in the
  test was 5 MB alone.
- **The authors table gets big fast.** The test's 100 works produced about
  32,000 author rows (6 MB), almost all from a few physics and genomics papers
  with thousands of authors each.
- **Hidden 100-author limit.** Search results list at most 100 authors per
  work. In the test, 28 of 100 works hit this, and for some the UCSD author
  came after position 100. `fetch_works.py` looks those works up again one by
  one so every author is kept. A simple script would quietly undercount UCSD
  researchers.
- **Counts move week to week.** The total dropped by 150 between 2026-11-04 and
  2026-11-09, and 2026 dropped by about 1,900 while every other year went up.
  OpenAlex seems to be moving works out of 2026 as dates get corrected.
  Record the date of every download.
- **FWCI changes constantly.** In the spot check, 12 of 25 works had a slightly
  different FWCI a few seconds after the download. Treat FWCI as approximate.
- **Not resumable.** If the download is interrupted, rerun it from the start.
  At about $0.13 a run, that's cheap.

## Questions for the team

- **Counts differ from OQL.** The API gives about 131,000 works; the OQL web
  interface gave about 135,600 for the same four organizations and years.
  The gap is about 3% and shows up in every year. Is the web interface
  counting something the API filter doesn't?
- **Which work types count?** Datasets are 17% of all works. Should datasets,
  preprints, conference abstracts, and errata be included?
- **Are UCSD Health System and Moores Cancer Center in scope?** OpenAlex lists
  them separately, and they aren't in our four.

`data/` is gitignored, so downloads are never uploaded to GitHub.
