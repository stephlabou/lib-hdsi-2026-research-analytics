"""
02_flatten.py -- convert the folder of OpenAlex JSON files into flat CSV tables.

Why several tables instead of one?
  A work has many authors, topics and funders. One row per work can't hold
  that without cramming lists into cells, so we make one table per "one-to-many"
  relationship and link them with the work_id column (like a small database).

Tables written to data/<run>/tables/
  works.csv        one row per work (title, year, type, citations, OA status, journal, publisher, main topic)
  authorships.csv  one row per work x author x institution   (is_ucsd = 1 if the institution is one of our RORs)
  topics.csv       one row per work x topic (up to 3 per work)
  funders.csv      one row per work x funder
  citations_by_year.csv   one row per work x calendar year (citations received that year)

Usage
  python 02_flatten.py
"""
import csv
import json
import os
import sys

from config import RAW_DIR, TABLE_DIR, ROR_IDS, short_id

# The set of ROR IDs we treat as "UC San Diego" (short form, e.g. 0168r3w48)
UCSD_RORS = {short_id(r) for r in ROR_IDS.values() if r and not r.startswith("TODO")}


def get(obj, *keys):
    """Safely dig into nested dicts: get(w, 'primary_location', 'source', 'id').
    Returns None if any level is missing or null (OpenAlex has many nulls)."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


WORK_COLS = [
    "work_id", "doi", "title", "publication_year", "publication_date", "type",
    "cited_by_count", "is_oa", "oa_status", "language", "is_retracted",
    "source_id", "source_name", "source_type", "publisher_id", "publisher",
    "primary_topic_id", "primary_topic", "primary_topic_subfield",
    "primary_topic_field", "primary_topic_domain",
    "n_authorships", "is_authors_truncated",
]
AUTHORSHIP_COLS = [
    "work_id", "author_position", "author_id", "author_name", "orcid",
    "is_corresponding", "institution_id", "institution_ror", "institution_name",
    "institution_country_code", "is_ucsd",
]
TOPIC_COLS = ["work_id", "is_primary", "topic_id", "topic", "subfield", "field", "domain", "score"]
FUNDER_COLS = ["work_id", "funder_id", "funder"]
CITES_COLS = ["work_id", "year", "cited_by_count"]


def flatten_work(w):
    """Turn one work (a dict) into rows for each table."""
    wid = short_id(w.get("id"))
    src = get(w, "primary_location", "source") or {}
    topic = w.get("primary_topic") or {}
    authorships = w.get("authorships") or []

    work_row = {
        "work_id": wid,
        "doi": w.get("doi"),
        "title": w.get("title") or w.get("display_name"),
        "publication_year": w.get("publication_year"),
        "publication_date": w.get("publication_date"),
        "type": w.get("type"),
        "cited_by_count": w.get("cited_by_count"),
        "is_oa": int(bool(get(w, "open_access", "is_oa"))),
        "oa_status": get(w, "open_access", "oa_status"),
        "language": w.get("language"),
        "is_retracted": int(bool(w.get("is_retracted"))),
        "source_id": short_id(src.get("id")),
        "source_name": src.get("display_name"),
        "source_type": src.get("type"),
        "publisher_id": short_id(src.get("host_organization")),
        "publisher": src.get("host_organization_name"),
        "primary_topic_id": short_id(topic.get("id")),
        "primary_topic": topic.get("display_name"),
        "primary_topic_subfield": get(topic, "subfield", "display_name"),
        "primary_topic_field": get(topic, "field", "display_name"),
        "primary_topic_domain": get(topic, "domain", "display_name"),
        "n_authorships": len(authorships),
        "is_authors_truncated": int(bool(w.get("is_authors_truncated"))),
    }

    # --- authorships: one row per author x institution -----------------------
    author_rows = []
    for a in authorships:
        author = a.get("author") or {}
        institutions = a.get("institutions") or [None]   # keep authors with no institution
        for inst in institutions:
            inst = inst or {}
            ror = short_id(inst.get("ror"))
            author_rows.append({
                "work_id": wid,
                "author_position": a.get("author_position"),
                "author_id": short_id(author.get("id")),
                "author_name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "is_corresponding": int(bool(a.get("is_corresponding"))),
                "institution_id": short_id(inst.get("id")),
                "institution_ror": ror,
                "institution_name": inst.get("display_name"),
                "institution_country_code": inst.get("country_code"),
                "is_ucsd": int(ror in UCSD_RORS) if ror else 0,
            })

    # --- topics ----------------------------------------------------------------
    topic_rows = []
    for i, t in enumerate(w.get("topics") or []):
        topic_rows.append({
            "work_id": wid, "is_primary": int(i == 0),
            "topic_id": short_id(t.get("id")), "topic": t.get("display_name"),
            "subfield": get(t, "subfield", "display_name"),
            "field": get(t, "field", "display_name"),
            "domain": get(t, "domain", "display_name"),
            "score": t.get("score"),
        })

    # --- funders (the old 'grants' field was removed from OpenAlex) -----------
    funder_rows = [{"work_id": wid, "funder_id": short_id(f.get("id")), "funder": f.get("display_name")}
                   for f in (w.get("funders") or [])]

    cite_rows = [{"work_id": wid, "year": c.get("year"), "cited_by_count": c.get("cited_by_count")}
                 for c in (w.get("counts_by_year") or [])]

    return work_row, author_rows, topic_rows, funder_rows, cite_rows


def main():
    files = sorted(p for p in RAW_DIR.glob("W*.json"))
    if not files:
        sys.exit(f"No W*.json files found in {RAW_DIR}. Run 01_download.py first.")
    if not UCSD_RORS:
        sys.exit("No ROR IDs set in config.py")

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    specs = {
        "works": WORK_COLS, "authorships": AUTHORSHIP_COLS, "topics": TOPIC_COLS,
        "funders": FUNDER_COLS, "citations_by_year": CITES_COLS,
    }
    handles, writers = {}, {}
    for name, cols in specs.items():
        handles[name] = open(TABLE_DIR / f"{name}.csv", "w", newline="", encoding="utf-8")
        writers[name] = csv.DictWriter(handles[name], fieldnames=cols)
        writers[name].writeheader()

    n_ok, n_bad = 0, 0
    # We read ONE file at a time and write straight to disk, so memory use stays
    # small no matter how many works there are.
    for i, path in enumerate(files, 1):
        try:
            with open(path, encoding="utf-8") as f:
                work = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  skipped {path.name}: {e}")
            n_bad += 1
            continue
        w_row, a_rows, t_rows, f_rows, c_rows = flatten_work(work)
        writers["works"].writerow(w_row)
        writers["authorships"].writerows(a_rows)
        writers["topics"].writerows(t_rows)
        writers["funders"].writerows(f_rows)
        writers["citations_by_year"].writerows(c_rows)
        n_ok += 1
        if i % 5000 == 0:
            print(f"  ...{i:,} of {len(files):,} files")

    for h in handles.values():
        h.close()

    raw_bytes = sum(p.stat().st_size for p in files)
    csv_bytes = {n: os.path.getsize(TABLE_DIR / f"{n}.csv") for n in specs}
    print(f"\nConverted {n_ok:,} works ({n_bad} skipped).")
    print("\n=== Size comparison ===")
    print(f"Raw JSON ({len(files):,} files): {raw_bytes / 1e6:,.1f} MB")
    for n, b in csv_bytes.items():
        print(f"  {n + '.csv':<24}{b / 1e6:>10,.1f} MB")
    print(f"  {'CSV total':<24}{sum(csv_bytes.values()) / 1e6:>10,.1f} MB")


if __name__ == "__main__":
    main()
