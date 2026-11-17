# OpenAlex via the Web Interface with OQL

This folder documents the web interface with OQL approach for pulling UC San Diego content from OpenAlex (workflow part 1) and converting it to tabular format (workflow part 2).

## What does this approach do?

Uses the OpenAlex website's OQL search tab to select all works affiliated with UCSD and related organizations from 2020 to 2026, exports the results as a CSV, and converts the CSV into tidy tables with `convert_export.py`.

OQL docs: https://help.openalex.org/access/oql/

## The query

**Dates run:** 2026-11-03 (counts and test export) and 2026-11-16 (full export)

**Organizations (OpenAlex institution IDs):**

| Organization | OpenAlex ID |
| --- | --- |
| University of California San Diego | I36258959 |
| San Diego Supercomputer Center | I181653535 |
| Scripps Institution of Oceanography | I150209017 |
| University of California San Diego Medical Center | I4210132395 |

**Time range:** 2020 - 2026

**Exact OQL text:**

```
get works from 2020–2026 from [University of California San Diego](I36258959) or [San Diego Supercomputer Center](I181653535) or [Scripps Institution of Oceanography](I150209017) or [University of California San Diego Medical Center](I4210132395)
```

## Results

**Total works returned:** 135,577 on 2026-11-03. On 2026-11-16 the same query returned **131,927** works (the export dialog and the exported file both show this number). OpenAlex is updated continuously, so counts change between runs. The year and type tables below are from 2026-11-03 and add up to 135,577.

**Works per year** (as of 2026-11-03; modify the query to group by year, shown below):

```
get the count of works from [University of California San Diego](I36258959) or [San Diego Supercomputer Center](I181653535) or [Scripps Institution of Oceanography](I150209017) or [University of California San Diego Medical Center](I4210132395) by year from 2020–2026
```

| Year | Works |
| --- | --- |
| 2020 | 20,679 |
| 2021 | 18,383 |
| 2022 | 18,008 |
| 2023 | 18,529 |
| 2024 | 18,600 |
| 2025 | 18,237 |
| 2026 (partial) | 23,141 |

2026 is only a partial year but has more works than any full year. (not sure why)

**Works per type** (as of 2026-11-03; modify the query to group by type, shown below):

```
get the count of works from 2020–2026 from [University of California San Diego](I36258959) or [San Diego Supercomputer Center](I181653535) or [Scripps Institution of Oceanography](I150209017) or [University of California San Diego Medical Center](I4210132395) by type
```

| Type | Works |
| --- | --- |
| article | 69,491 |
| dataset | 21,858 |
| preprint | 9,770 |
| conference-paper | 7,007 |
| conference-abstract | 6,544 |
| other | 5,851 |
| review | 5,838 |
| book-chapter | 3,256 |
| editorial | 1,671 |
| erratum | 865 |
| peer-review | 621 |
| report | 581 |
| letter | 528 |
| book-review | 273 |
| paratext | 271 |
| book | 249 |
| reference-entry | 229 |
| software | 221 |
| supplementary-materials | 213 |
| data-paper | 83 |
| standard | 59 |
| dissertation | 45 |
| retraction | 37 |
| software-paper | 16 |

The type counts add up to 135,577, the same as the number of works in the full query.

**Each organization alone** (as of 2026-11-03, to see overlap between the four):

| Organization | Works |
| --- | --- |
| University of California San Diego | 135,577 |
| San Diego Supercomputer Center | 740 |
| Scripps Institution of Oceanography | 8,771 |
| UC San Diego Medical Center | 650 |

The UCSD query alone returns 135,577 works, the same as the combined query. So SDSC, SIO, and the Medical Center add no works beyond UCSD: every work found for those three is already in the UCSD results. Adding the four counts gives 145,738, which overcounts by 10,161, exactly the total of the three smaller organizations.

## How to run and export

1. Go to https://openalex.org and open the OQL tab at the top of the search page.
2. Paste the OQL text from above and run it. The result count appears with the results.
3. Open the export dialog. The export button looks like a download sign. The dialog shows the row count and an estimated cost, and lets you choose:
   - **Format:** CSV (Excel), CSV, Endnote, BibTeX, or Text. Used: CSV
   - **Include abstracts:** off, since the file size is dramatically increased
   - **Columns:** the picker offers 97 columns in 11 categories (Aboutness, Author, Source, Funder, Institution, Geo, Open Access, and others).
4. Start the export and save the file in a `data/` folder next to the script. The `data/` folder is in `.gitignore`.

**Columns used:** all columns were exported. The resulting CSV has 105 columns, and the script reads the 23 it needs: Work ID, DOI, Title, Year, Type, Citation count, Open access, Open Access status, Source, Source IDs, Domain, Field, Topic, Is paratext, Retracted, Author, Author IDs, ORCID, Country, Institution, Institution IDs, Funder, Funder IDs.

(The first test export used 24 columns: the 23 above plus ROR ID. ROR ID is not used; see findings.)

## Export notes (usability findings)

**Cost and size**
- The full export of 135,577 rows (on 2026-11-03) showed an estimated cost of about $0.136 of a remaining $0.978 budget, so exports are limited. The estimate did not change when columns were added or removed.
- **Full export: 688 MB** (131,927 works, 105 columns).

**File structure**
- Fields with many values are packed into one cell, separated by `|`. An empty slot is kept as `||`, so positions stay aligned.
- Author, Author IDs, and ORCID had the same number of entries in all 98 test works, but not in all works of the full export (538 of 131,927 differ; see conversion results).
- **Country does not line up with authors.** In 9 of the 98 test works it has more entries than there are authors (for example 163 entries for 100 authors). It appears to hold one entry per author affiliation, but there is no way to tell which author each entry belongs to. Countries are stored in their own table.
- Institution and Institution IDs are a deduplicated list per work, not one per author (for example 51 authors and 9 institutions on one work), so authors cannot be matched to institutions.
- ROR ID has a third count that matches neither the authors nor the institutions, and is not used.
- There is no publisher column, only Source (the journal). The top publishers table needs a separate lookup using Source IDs.
- Funder was blank for 29 of 98 test works (about 30%).
- Some columns hold text labels instead of true/false. In the full export the labels are "not is paratext" / "is paratext" and "Isn't retracted" / "Is retracted". The script converts them to True/False.
- "Open access" is a yes/no label, and "Open Access status" has the type (for example gold), which is the column needed for the open access breakdown.


## Format conversion (workflow part 2)

**Script:** `convert_export.py` (needs Python 3 with pandas)

**Guide:**
1. Save the downloaded CSV in the `data/` folder.
2. Near the top of the script, set `INPUT_NAME` to the new file's name, e.g. `INPUT_NAME = "works-2026-11-16T22-21-03.csv"`.
3. From the folder containing the script, run `python3 convert_export.py`.
4. The tables are written to `data/tables/`. Running it again overwrites them.

**What it does:** reads the export in chunks of 10,000 works (so the whole file never has to fit in memory), splits the `|`-separated cells, and writes tables to `data/tables/`. It converts the paratext and retracted labels to True/False, drops duplicate Work IDs, reports any works whose columns don't line up (also saved to `data/tables/misaligned_works.csv`), and prints table sizes and run time.

**Tables** (all linked by `Work ID`):

| Table | One row per | Columns |
| --- | --- | --- |
| works | work | Work ID, DOI, Title, Year, Type, Citation count, Open access, Open Access status, Source, Source IDs, Domain, Field, Topic, Is paratext, Retracted |
| work_authors | author per work | Work ID, Position, Author, Author ID, ORCID |
| work_countries | country entry per work | Work ID, Position, Country |
| work_institutions | institution per work | Work ID, Position, Institution, Institution ID |
| work_funders | funder per work | Work ID, Position, Funder, Funder ID |

**Results on the full export (2026-11-16):** 131,927 works read, 0 duplicates, 9.6 seconds.

| Table | Rows | Size |
| --- | --- | --- |
| works | 131,927 | 41.83 MB |
| work_authors | 1,649,609 | 120.92 MB |
| work_countries | 2,966,770 | 55.21 MB |
| work_institutions | 900,384 | 48.42 MB |
| work_funders | 299,508 | 18.66 MB |

- 49 works are labeled paratext and 29 are labeled retracted.
- **538 works (0.4%) were skipped from work_authors** because Author, Author IDs, and ORCID had different numbers of entries. 
- 1,150 works have institution names that don't match the institution IDs. They are kept with IDs only and blank names. 73 works have the same issue for funders.


## Problems

- No publisher column, no author-to-institution link, a Country column that doesn't line up with authors, and funder blank for about 30% of works in the test export.


## Data

The full export (688 MB) and the converted tables are not stored in this repo. They live in the `data/` folder, which is in `.gitignore`. Do not add the restricted UCSD-only faculty departmental data to this repo.