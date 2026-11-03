# OpenAlex via the Web Interface with OQL

This branch documents the web interface with OQL approach for pulling UC San Diego content (https://docs.google.com/spreadsheets/d/1Xl57Z2alFMfAEM4kl-07jEZIHma6Q_mf/edit?gid=1036025528#gid=1036025528) from OpenAlex (workflow part 1) and converting it to tabular format (workflow part 2). 

## What does this approach do?

Uses the OpenAlex website's OQL search tab to select all works affiliated with UCSD and related organizations from 2020 to 2026, then exports the results for conversion to tables.

OQL docs: https://help.openalex.org/access/oql/




```
get works from 2020–2026 from [University of California San Diego](I36258959) or [San Diego Supercomputer Center](I181653535) or [Scripps Institution of Oceanography](I150209017) or [University of California San Diego Medical Center](I4210132395)
```

