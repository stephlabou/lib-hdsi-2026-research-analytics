# OpenAlex via the Web Interface with OQL

This branch documents the web interface with OQL approach for pulling UC San Diego content (https://docs.google.com/spreadsheets/d/1Xl57Z2alFMfAEM4kl-07jEZIHma6Q_mf/edit?gid=1036025528#gid=1036025528) from OpenAlex (workflow part 1) and converting it to tabular format (workflow part 2). 

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

**Total works returned:** about 135,600 (as shown by the web interface on 2026-11-03). Counts change as OpenAlex updates, so rerun the query to verify.

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

The type counts add up to 135,577, compared with about 135,600 works in the full query. [Add a note if they don't match, e.g. works with no type listed.]

**Each organization alone** (to see overlap between the four):

| Organization | Works |
| --- | --- |
| University of California San Diego | 135,577 |
| San Diego Supercomputer Center | 740 |
| Scripps Institution of Oceanography | 8,771 |
| UC San Diego Medical Center | 650 |

Counts for each organization alone sum to 145,738, compared with about 135,600 works in the combined query, so about 10,000 works are affiliated with more than one of the four organizations.

## How to run and export
