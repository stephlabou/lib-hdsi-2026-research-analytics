"""Step 2: flatten the downloaded works into CSV tables.

Each nested part of a work goes into its own table, linked by work_id:

    works.csv        one row per work (bibliographic, citation, OA, venue, primary topic)
    authorships.csv  one row per work x author x institution (authors with no
                     institution get one row with blank institution fields)
    funders.csv      one row per work x funder
    topics.csv       one row per work x topic (with subfield / field / domain)

How to run (from the repository's top folder):
    python api_query/to_tables.py data/raw/ucsd_works.jsonl.gz --out-dir data/tables
"""

import argparse
import csv
import gzip
import json
from pathlib import Path

from config import INSTITUTIONS

# Institution IDs as they appear inside work records.
UCSD_IDS = {f"https://openalex.org/{i}" for i in INSTITUTIONS.values()}

WORK_COLS = [
    "work_id", "doi", "title", "publication_year", "publication_date", "type", "language",
    "cited_by_count", "fwci", "is_retracted",
    "is_oa", "oa_status", "oa_url",
    "source_id", "source_name", "source_type", "issn_l",
    "publisher_id", "publisher_name",
    "primary_topic", "primary_subfield", "primary_field", "primary_domain",
    "n_authors", "n_ucsd_authors", "countries_distinct_count", "institutions_distinct_count",
]
AUTHORSHIP_COLS = [
    "work_id", "author_order", "author_position", "author_id", "author_name", "raw_author_name", "orcid",
    "is_corresponding", "institution_id", "institution_name", "institution_ror",
    "institution_country", "institution_type", "is_ucsd_affiliation",
]
FUNDER_COLS = ["work_id", "funder_id", "funder_name", "funder_ror"]
TOPIC_COLS = ["work_id", "topic_id", "topic", "score", "subfield", "field", "domain"]


def short_id(url):
    """https://openalex.org/W123 -> W123 (keeps tables smaller)."""
    return url.rsplit("/", 1)[-1] if url else None


def name(obj):
    """display_name of a nested object, or None if the object is missing."""
    return (obj or {}).get("display_name")


def work_row(w):
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    pt = w.get("primary_topic") or {}
    authorships = w.get("authorships") or []
    # An author counts as UCSD if any of their listed institutions is one of ours.
    n_ucsd = sum(
        any(i.get("id") in UCSD_IDS for i in a.get("institutions") or [])
        for a in authorships
    )
    return {
        "work_id": short_id(w["id"]),
        "doi": w.get("doi"),
        "title": w.get("title"),
        "publication_year": w.get("publication_year"),
        "publication_date": w.get("publication_date"),
        "type": w.get("type"),
        "language": w.get("language"),
        "cited_by_count": w.get("cited_by_count"),
        "fwci": w.get("fwci"),
        "is_retracted": w.get("is_retracted"),
        "is_oa": oa.get("is_oa"),
        "oa_status": oa.get("oa_status"),
        "oa_url": oa.get("oa_url"),
        "source_id": short_id(src.get("id")),
        "source_name": src.get("display_name"),
        "source_type": src.get("type"),
        "issn_l": src.get("issn_l"),
        "publisher_id": short_id(src.get("host_organization")),
        "publisher_name": src.get("host_organization_name"),
        "primary_topic": pt.get("display_name"),
        "primary_subfield": name(pt.get("subfield")),
        "primary_field": name(pt.get("field")),
        "primary_domain": name(pt.get("domain")),
        "n_authors": len(authorships),
        "n_ucsd_authors": n_ucsd,
        "countries_distinct_count": w.get("countries_distinct_count"),
        "institutions_distinct_count": w.get("institutions_distinct_count"),
    }


def authorship_rows(w):
    wid = short_id(w["id"])
    # author_order is 1 for the first listed author, 2 for the second, etc.
    for order, a in enumerate(w.get("authorships") or [], start=1):
        author = a.get("author") or {}
        base = {
            "work_id": wid,
            "author_order": order,
            "author_position": a.get("author_position"),
            "author_id": short_id(author.get("id")),
            "author_name": author.get("display_name"),
            "raw_author_name": a.get("raw_author_name"),
            "orcid": author.get("orcid"),
            "is_corresponding": a.get("is_corresponding"),
        }
        # One row per institution; [{}] gives one blank row if there are none.
        for inst in a.get("institutions") or [{}]:
            yield {
                **base,
                "institution_id": short_id(inst.get("id")),
                "institution_name": inst.get("display_name"),
                "institution_ror": inst.get("ror"),
                "institution_country": inst.get("country_code"),
                "institution_type": inst.get("type"),
                "is_ucsd_affiliation": inst.get("id") in UCSD_IDS,
            }


def funder_rows(w):
    wid = short_id(w["id"])
    for f in w.get("funders") or []:
        yield {
            "work_id": wid,
            "funder_id": short_id(f.get("id")),
            "funder_name": f.get("display_name"),
            "funder_ror": f.get("ror"),
        }


def topic_rows(w):
    wid = short_id(w["id"])
    for t in w.get("topics") or []:
        yield {
            "work_id": wid,
            "topic_id": short_id(t.get("id")),
            "topic": t.get("display_name"),
            "score": t.get("score"),
            "subfield": name(t.get("subfield")),
            "field": name(t.get("field")),
            "domain": name(t.get("domain")),
        }


# table name -> (columns, function that turns one work into that table's rows)
TABLES = {
    "works": (WORK_COLS, lambda w: [work_row(w)]),
    "authorships": (AUTHORSHIP_COLS, authorship_rows),
    "funders": (FUNDER_COLS, funder_rows),
    "topics": (TOPIC_COLS, topic_rows),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="gzipped JSONL from fetch_works.py")
    ap.add_argument("--out-dir", default="data/tables")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Open all four CSVs at once so the input file is read only one time.
    files, writers, counts = {}, {}, {}
    for tname, (cols, _) in TABLES.items():
        files[tname] = open(out_dir / f"{tname}.csv", "w", newline="", encoding="utf-8")
        writers[tname] = csv.DictWriter(files[tname], fieldnames=cols)
        writers[tname].writeheader()
        counts[tname] = 0

    try:
        with gzip.open(args.input, "rt", encoding="utf-8") as f:
            for line in f:
                w = json.loads(line)
                for tname, (_, rows) in TABLES.items():
                    for row in rows(w):
                        writers[tname].writerow(row)
                        counts[tname] += 1
    finally:
        for fh in files.values():
            fh.close()

    for tname in TABLES:
        path = out_dir / f"{tname}.csv"
        print(f"{path}: {counts[tname]:,} rows, {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
