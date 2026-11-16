# OpenAlex via the Web Interface with OQL

This branch documents the web interface with OQL approach for pulling UC San Diego content from OpenAlex (workflow part 1) and converting it to tabular format (workflow part 2). 

## What does this approach do?

Uses the OpenAlex website's OQL search tab to select all works affiliated with UCSD and related organizations from 2020 to 2026, then exports the results for conversion to tables.

OQL docs: https://help.openalex.org/access/oql/


## The query

**Date run:** 2026-11-03

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

**Total works returned:** 135,577 (shown in the export dialog on 2026-11-03). The year counts and the type counts below each add up to this number. Counts change as OpenAlex updates, can rerun query to double check.

**Works per year** (modify query to group by year, modification shown below):

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

**Works per type** (articles, preprints, datasets, etc.) (modify query to group by type, modification shown below):

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

The type counts add up to 135,577, same as the amount of works in the full query. 

**Each organization alone** (to see overlap between the four):

| Organization | Works |
| --- | --- |
| University of California San Diego | 135,577 |
| San Diego Supercomputer Center | 740 |
| Scripps Institution of Oceanography | 8,771 |
| UC San Diego Medical Center | 650 |

The UCSD query alone returns 135,577 works, which is the same as the combined query. So SDSC, SIO, and the Medical Center don't add works beyond UCSD (every work found for those three is already in the UCSD (about 10,000) results).

## How to run and export

1. Go to https://openalex.org and open the OQL tab at the top of the search page.
2. Paste the OQL text from above and run it. The result count appears with the results.
3. Open the export dialog. The export button looks like the download sign. The dialog shows the row count and an estimated cost, and lets you choose:
   - **Format:** CSV (Excel), CSV, Endnote, BibTeX, or Text. Used: CSV
   - **Include abstracts:** off, since file size will be dramatically increased
   - **Columns:** 97 columns total columns in 11 categories (Aboutness, Author, Source, Funder, Institution, Geo, Open Access, and others).
4. Start the export and save the file in a `data/` folder next to the script. The `data/` folder is in `.gitignore`.

**INCLUDE ALL COLUMNS**

Previous Columns chosen (24): Title, Author, Year, Citation count, Open access, ROR ID, Work ID, ORCID, DOI, Type, Author IDs, Institution, Institution IDs, Country, Source, Source IDs, Funder, Funder IDs, Domain, Field, Topic, Open Access status, Is paratext, Retracted



## Export notes (usability findings)
**Cost and size**
- The full export of 135,577 rows showed an estimated cost of about $0.136 of a remaining $0.978 budget, so exports are limited. The estimate did not change when columns were added or removed.
- Test export (a small filtered query, ```get works where institution is (I181653535) and year is (2024)```): 98 works, 24 columns, 0.18 MB. Extrapolating at about 1.8 KB per work gives roughly 250 MB for the full export. This is a rough estimate, since the test works may not be typical.
- Full export size: 


## Format conversion (workflow part 2)
 
**Script:** `convert_export.py`
 
**What it does:** reads the export, splits the `|`-separated cells, and writes tables to `data/tables/`. It converts the paratext and retracted labels to True/False, drops duplicate Work IDs, reports any works whose columns don't line up, and prints table sizes and run time.
 
**Tables** (all linked by `Work ID`):
 
| Table | One row per | Columns |
| --- | --- | --- |
| works | work | Work ID, DOI, Title, Year, Type, Citation count, Open access, Open Access status, Source, Source IDs, Domain, Field, Topic, Is paratext, Retracted |
| work_authors | author per work | Work ID, Position, Author, Author ID, ORCID |
| work_countries | country entry per work | Work ID, Position, Country |
| work_institutions | institution per work | Work ID, Position, Institution, Institution ID |
| work_funders | funder per work | Work ID, Position, Funder, Funder ID |
 
Notes on use:
- Sum citations from the works table only. Summing after a join to work_authors counts each work once per author.
- Works with misaligned author columns are skipped and reported (none expected). For institutions and funders, misaligned works keep their IDs with blank names.
- Institution names for those works can be filled in from other works that share the same Institution ID.
**Results on the 98-work test export:** **[FILL IN: rows and size of each table, and any warnings]**
 
**Results on the full export:** **TODO**

### NOTE: 
- No publisher column, no author-to-institution link, a Country column that doesn't line up with authors, and funder blank for about 30% of works in the test export.