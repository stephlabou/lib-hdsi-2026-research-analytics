"""Step 3: check the CSV tables against OpenAlex to confirm they are accurate.

Two checks:

1. Year totals: counts works per publication year in works.csv and compares
   them with what OpenAlex reports for the same query (one group_by request).
   Only meaningful after a full download; a --max-pages test download will
   show large gaps here, which is expected.

2. Spot check: picks random works from works.csv, looks each one up in
   OpenAlex again, and compares the fields we extracted. It also checks that
   authorships.csv has one row per author for those works.
   cited_by_count and fwci can legitimately change between the download and
   the check, so those are reported as "changed", not as errors.

How to run (from the repository's top folder):
    python api_query/check_tables.py --tables data/tables --sample 25
"""

import argparse
import os
import random
import sys

import pandas as pd
import requests

from config import API_BASE, WORKS_FILTER, YEAR_END, YEAR_START
from to_tables import work_row

# Fields that can change on OpenAlex's side after the download.
DRIFTING_FIELDS = {"cited_by_count", "fwci"}


def check_year_totals(works, session, api_key):
    print("== Year totals: works.csv vs OpenAlex ==")
    params = {"filter": WORKS_FILTER, "group_by": "publication_year"}
    if api_key:
        params["api_key"] = api_key
    groups = session.get(f"{API_BASE}/works", params=params, timeout=60).json()["group_by"]
    api_counts = {int(g["key"]): g["count"] for g in groups}
    ours = works["publication_year"].value_counts().to_dict()

    ok = True
    for year in range(YEAR_START, YEAR_END + 1):
        a, o = api_counts.get(year, 0), ours.get(year, 0)
        # OpenAlex adds works daily, so allow a small gap (0.5%).
        flag = "" if abs(a - o) <= max(5, 0.005 * a) else "  <-- mismatch"
        ok = ok and not flag
        print(f"  {year}: tables {o:>7,}   OpenAlex {a:>7,}{flag}")
    return ok


def same(a, b):
    """Compare a CSV value with a freshly computed one (CSV turns everything into text/NaN)."""
    if pd.isna(a) and b is None:
        return True
    if isinstance(b, bool):
        return str(a) == str(b)
    if isinstance(b, (int, float)) and not pd.isna(a):
        return abs(float(a) - float(b)) < 1e-6
    return str(a) == str(b)


def spot_check(works, authorships, session, api_key, n):
    print(f"\n== Spot check: {n} random works re-fetched from OpenAlex ==")
    ids = random.sample(list(works["work_id"]), min(n, len(works)))
    rows = works.set_index("work_id")
    # One author can have several institution rows, so count distinct author_order.
    author_counts = authorships.drop_duplicates(["work_id", "author_order"]).groupby("work_id").size()
    params = {"api_key": api_key} if api_key else {}

    errors, drift = 0, 0
    for wid in ids:
        fresh = session.get(f"{API_BASE}/works/{wid}", params=params, timeout=60).json()
        expected = work_row(fresh)
        ours = rows.loc[wid]
        for col, val in expected.items():
            if col == "work_id" or same(ours[col], val):
                continue
            if col in DRIFTING_FIELDS:
                drift += 1
                print(f"  {wid} {col}: changed since download ({ours[col]} -> {val})")
            else:
                errors += 1
                print(f"  {wid} {col}: MISMATCH tables={ours[col]!r} OpenAlex={val!r}")
        if author_counts.get(wid, 0) != expected["n_authors"]:
            errors += 1
            print(f"  {wid} authorships.csv has {author_counts.get(wid, 0)} authors, "
                  f"OpenAlex has {expected['n_authors']}")

    print(f"  {len(ids)} works checked: {errors} mismatches, {drift} citation-count changes")
    return errors == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", default="data/tables", help="folder written by to_tables.py")
    ap.add_argument("--sample", type=int, default=25, help="how many works to spot check")
    ap.add_argument("--seed", type=int, default=None, help="random seed, to repeat the same spot check")
    args = ap.parse_args()
    random.seed(args.seed)

    api_key = os.environ.get("OPENALEX_API_KEY")
    works = pd.read_csv(f"{args.tables}/works.csv")
    authorships = pd.read_csv(f"{args.tables}/authorships.csv", usecols=["work_id", "author_order"])
    session = requests.Session()

    totals_ok = check_year_totals(works, session, api_key)
    spot_ok = spot_check(works, authorships, session, api_key, args.sample)

    print("\nResult:", "all checks passed" if totals_ok and spot_ok else "see issues above")
    sys.exit(0 if totals_ok and spot_ok else 1)


if __name__ == "__main__":
    main()
