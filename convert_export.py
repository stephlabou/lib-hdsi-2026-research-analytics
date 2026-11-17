"""
Convert an OpenAlex web-interface export (CSV) into tidy tables.

Why this is needed:
  The export has one row per work, but some columns (authors, institutions,
  funders) hold many values packed into one cell, separated by "|".
  This script splits those cells so each value gets its own row.

Tables written (to data/tables/):
  works.csv              one row per work
  work_authors.csv       one row per author per work (name, ID, ORCID)
  work_countries.csv     one row per country entry per work (see note below)
  work_rors.csv          one row per ROR ID entry per work (see note below)
  work_institutions.csv  one row per institution per work
  work_funders.csv       one row per funder per work

All tables share the "Work ID" column, so they can be joined back together.

Note on countries: the export's Country column does NOT always have one entry per
author (some works list more countries than authors, probably because an author can
have several affiliations). So countries are kept in their own table and are not
tied to a specific author.

Note on ROR IDs: the ROR ID column has its own count, different from the authors and
from the institutions (it looks like one entry per author affiliation, with repeats).
It is kept in its own table, in its original order and with repeats, and is not tied
to a specific author or institution.

The export is read in chunks of CHUNK_SIZE works, so the full export (hundreds of
MB) does not have to fit in memory at once.

How to run:
  python3 convert_export.py
Change INPUT_NAME below to point at a different export file.
Running it again overwrites the tables from the previous run.
"""

import time
from collections import Counter
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Folder containing this script (or the current folder, when run in a notebook)
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

INPUT_NAME = "works-2026-11-16T22-21-03.csv"   # the export file inside data/
INPUT_PATH = BASE_DIR / "data" / INPUT_NAME
OUTPUT_DIR = BASE_DIR / "data" / "tables"      # data/ is in .gitignore, so nothing here is committed

SEPARATOR = "|"      # the export separates multiple values in one cell with "|"
CHUNK_SIZE = 10_000  # works processed at a time; lower this if memory is a problem

# Columns that hold one value per work
WORK_COLUMNS = [
    "Work ID", "DOI", "Title", "Year", "Type", "Citation count",
    "Open access", "Open Access status",
    "Source", "Source IDs", "Domain", "Field", "Topic",
    "Is paratext", "Retracted",
]

# Every column the script uses. If the export has more columns than these, the extra
# ones are ignored (they are never loaded, which keeps memory use and run time down).
NEEDED_COLUMNS = WORK_COLUMNS + [
    "Author", "Author IDs", "ORCID", "Country", "ROR ID",
    "Institution", "Institution IDs", "Funder", "Funder IDs",
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def split_cell(value):
    """Split one cell into a list of values. A blank cell becomes an empty list.
    Empty slots between separators (like 'a||c') are kept as '' so positions stay aligned."""
    if pd.isna(value):
        return []
    return str(value).split(SEPARATOR)


def explode_columns(df, columns, new_names, id_column=None, drop_blank_rows=False):
    """Turn columns of packed values into one row per value.

    columns         : the export columns to split (their values must line up by position)
    new_names       : names for those columns in the new table
    id_column       : (optional) which of `columns` (0 = first) holds IDs. If a work's columns
                      don't line up, the IDs are still kept and the other columns are left
                      blank, instead of dropping the whole work.
    drop_blank_rows : (optional) skip empty slots where every value is blank

    Without id_column, works whose columns have different numbers of values are skipped,
    so misaligned data never ends up in the table silently.

    Returns (table, skipped, partial): the table, plus the works that were skipped and the
    works that were kept with IDs only. Each of those is a (Work ID, details) pair, where
    the details show how many entries each column had, e.g. "Author=5; Author IDs=4".
    """
    # Build the table one column at a time (uses less memory than building row by row)
    out = {"Work ID": [], "Position": []}
    for name in new_names:
        out[name] = []
    skipped = []
    partial = []

    for work_id, *cells in zip(df["Work ID"], *(df[c] for c in columns)):
        lists = [split_cell(cell) for cell in cells]
        raw_counts = [len(item) for item in lists]    # entries per column, before any padding
        n = max(len(item) for item in lists)
        if n == 0:
            continue                      # nothing to record for this work

        # A fully blank column (e.g. no ORCIDs at all) is padded with blanks
        lists = [item if item else [""] * n for item in lists]

        if any(len(item) != n for item in lists):
            detail = "; ".join(f"{c}={k}" for c, k in zip(columns, raw_counts))
            if id_column is None:
                skipped.append((work_id, detail))   # columns don't line up, so don't guess
                continue
            # Keep the IDs, leave the other columns blank
            ids = lists[id_column]
            n = len(ids)
            lists = [ids if k == id_column else [""] * n for k in range(len(lists))]
            partial.append((work_id, detail))

        for position in range(n):
            values = [item[position] for item in lists]
            if drop_blank_rows and not any(v.strip() for v in values):
                continue
            out["Work ID"].append(work_id)
            out["Position"].append(position + 1)
            for name, value in zip(new_names, values):
                out[name].append(value)

    return pd.DataFrame(out), skipped, partial


def label_to_bool(series):
    """Turn text labels like 'not is paratext' or "Isn't retracted" into True/False.
    Labels containing 'not' or "n't" are False; anything else (that isn't blank) is True.
    Blank cells stay blank. The label counts are printed at the end so you can confirm
    this matches the real labels."""
    negative = series.str.contains(r"\bnot\b|n't", case=False, na=False)
    result = (~negative).astype("boolean")   # "boolean" (lowercase) allows blank values
    result[series.isna()] = pd.NA
    return result


def file_size_mb(path):
    return round(path.stat().st_size / 1_000_000, 2)


def append_table(table, name, first_chunk):
    """Write a table's rows to its CSV file (the header only on the first chunk)."""
    path = OUTPUT_DIR / f"{name}.csv"
    table.to_csv(path, mode="w" if first_chunk else "a", header=first_chunk, index=False)

# ---------------------------------------------------------------------------
# Main steps
# ---------------------------------------------------------------------------

start = time.time()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TABLE_NAMES = ["works", "work_authors", "work_countries", "work_rors", "work_institutions", "work_funders"]
for name in TABLE_NAMES:
    (OUTPUT_DIR / f"{name}.csv").unlink(missing_ok=True)   # start fresh, so reruns don't pile up

print(f"Reading {INPUT_PATH.name} ({file_size_mb(INPUT_PATH)} MB) in chunks of {CHUNK_SIZE:,} works")

rows_read = 0
duplicates = 0
seen_ids = set()                                 # Work IDs already written, to catch duplicates
row_counts = Counter()                           # rows written per table
skipped = {name: [] for name in TABLE_NAMES}     # works dropped from a table
partial = {name: [] for name in TABLE_NAMES}     # works kept with IDs only
paratext_labels = Counter()
retracted_labels = Counter()

# Check the export has every column the script needs before reading it all
header = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", nrows=0).columns
missing = [c for c in NEEDED_COLUMNS if c not in header]
if missing:
    raise SystemExit(f"The export is missing these columns: {missing}\nColumns found: {list(header)}")
print(f"The export has {len(header)} columns; using the {len(NEEDED_COLUMNS)} the script needs")

# Everything is read as text, so IDs and codes are never changed by pandas
chunks = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", dtype=str, chunksize=CHUNK_SIZE,
                     usecols=NEEDED_COLUMNS)

for chunk_number, chunk in enumerate(chunks, start=1):
    first_chunk = chunk_number == 1
    rows_read += len(chunk)

    # Each work should appear only once (checked within and across chunks)
    is_new = ~chunk["Work ID"].duplicated() & ~chunk["Work ID"].isin(seen_ids)
    duplicates += int((~is_new).sum())
    chunk = chunk[is_new]
    seen_ids.update(chunk["Work ID"])

    # Works table: the columns that hold one value per work
    works = chunk[WORK_COLUMNS].copy()
    paratext_labels.update(works["Is paratext"].fillna("(blank)"))
    retracted_labels.update(works["Retracted"].fillna("(blank)"))
    works["Is paratext"] = label_to_bool(works["Is paratext"])
    works["Retracted"] = label_to_bool(works["Retracted"])

    # Tables for columns with many values per work
    results = {
        "works": (works, [], []),
        "work_authors": explode_columns(
            chunk, ["Author", "Author IDs", "ORCID"], ["Author", "Author ID", "ORCID"]),
        "work_countries": explode_columns(
            chunk, ["Country"], ["Country"], drop_blank_rows=True),
        "work_rors": explode_columns(
            chunk, ["ROR ID"], ["ROR ID"], drop_blank_rows=True),
        "work_institutions": explode_columns(
            chunk, ["Institution", "Institution IDs"], ["Institution", "Institution ID"],
            id_column=1, drop_blank_rows=True),
        "work_funders": explode_columns(
            chunk, ["Funder", "Funder IDs"], ["Funder", "Funder ID"],
            id_column=1, drop_blank_rows=True),
    }

    for name, (table, skipped_ids, partial_ids) in results.items():
        append_table(table, name, first_chunk)
        row_counts[name] += len(table)
        skipped[name].extend(skipped_ids)
        partial[name].extend(partial_ids)

    print(f"  chunk {chunk_number}: {rows_read:,} works read so far")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print(f"\nRead {rows_read:,} rows ({duplicates:,} duplicate Work IDs removed)")
print("\nIs paratext labels:", dict(paratext_labels))
print("Retracted labels:  ", dict(retracted_labels))

print("\nChecks:")
for name in TABLE_NAMES[1:]:
    if skipped[name]:
        print(f"  WARNING ({name}): skipped {len(skipped[name]):,} works with misaligned columns, e.g. {[w for w, _ in skipped[name][:3]]}")
    elif partial[name]:
        print(f"  NOTE ({name}): {len(partial[name]):,} works had misaligned columns; kept the IDs and left other columns blank, e.g. {[w for w, _ in partial[name][:3]]}")
    else:
        print(f"  OK ({name}): all columns lined up")

# Save the misaligned works to a file, so they can be looked at later
log_rows = []
for name in TABLE_NAMES[1:]:
    log_rows += [(name, w, "skipped", d) for w, d in skipped[name]]
    log_rows += [(name, w, "kept IDs only", d) for w, d in partial[name]]
log_path = OUTPUT_DIR / "misaligned_works.csv"
if log_rows:
    pd.DataFrame(log_rows, columns=["Table", "Work ID", "Outcome", "Entries per column"]).to_csv(log_path, index=False)
    print(f"\nMisaligned works are listed in {log_path.relative_to(BASE_DIR)}")
else:
    log_path.unlink(missing_ok=True)

print("\nTable sizes:")
for name in TABLE_NAMES:
    print(f"  {name}: {row_counts[name]:,} rows, {file_size_mb(OUTPUT_DIR / (name + '.csv'))} MB")

print(f"\nDone in {round(time.time() - start, 1)} seconds")