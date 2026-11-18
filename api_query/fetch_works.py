"""Step 1: download every OpenAlex work affiliated with UC San Diego (2020-2026).

What it does:
    Asks the OpenAlex API for all works matching the filter in config.py,
    100 works per request, and saves each work as one line of JSON in a
    gzipped file (.jsonl.gz).

How to run (from the repository's top folder):
    export OPENALEX_API_KEY=...   # free key: https://openalex.org/settings/api
    python api_query/fetch_works.py

    Quick test without a key (first 100 works only):
    python api_query/fetch_works.py --out data/raw/sample.jsonl.gz --max-pages 1

Things to know:
    - An API key is required. Without one OpenAlex only returns the first page.
    - A full pull is ~1,300 requests (~$0.13), inside the free key's $1/day.
    - OpenAlex lists at most 100 authors per work in search results. For works
      that hit that limit, the script asks for that single work again (single
      lookups are free) so large collaborations keep their full author list.
      Without this, some UCSD authors would be missing from the data.
"""

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

import requests

from config import API_BASE, WORKS_FILTER

# Search results list at most this many authors per work (an OpenAlex limit).
AUTHORSHIP_CAP = 100


def get_with_retry(session, url, params, max_tries=6):
    """GET a URL and return its JSON, waiting and retrying on temporary errors.

    429 means "too many requests"; 5xx are server hiccups. Each retry waits
    twice as long as the last (1s, 2s, 4s, ...). Any other error stops the script.
    """
    for attempt in range(max_tries):
        resp = session.get(url, params=params, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504):
            wait = 2 ** attempt
            print(f"  HTTP {resp.status_code}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Giving up after {max_tries} tries: {resp.status_code} {resp.text[:200]}")


def fetch_full_work(session, work_id, api_key):
    """Look up one work by ID. Unlike search results, this has every author."""
    params = {"api_key": api_key} if api_key else {}
    short_id = work_id.rsplit("/", 1)[-1]  # https://openalex.org/W123 -> W123
    return get_with_retry(session, f"{API_BASE}/works/{short_id}", params)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/ucsd_works.jsonl.gz", help="where to save the download")
    ap.add_argument("--max-pages", type=int, default=None, help="stop after N pages of 100 (for testing)")
    args = ap.parse_args()

    api_key = os.environ.get("OPENALEX_API_KEY")
    if not api_key and args.max_pages != 1:
        sys.exit("OPENALEX_API_KEY is not set. OpenAlex needs a key to page past the first 100 results; "
                 "get a free one at https://openalex.org/settings/api "
                 "(or pass --max-pages 1 to test without one).")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # "cursor=*" starts cursor paging, which is how OpenAlex lets you walk
    # through more than 10,000 results. per_page=100 is the maximum.
    params = {"filter": WORKS_FILTER, "per_page": 100, "cursor": "*"}
    if api_key:
        params["api_key"] = api_key

    session = requests.Session()
    url = f"{API_BASE}/works"
    n_works, pages, cost, refetched = 0, 0, 0.0, 0
    start = time.time()

    with gzip.open(out, "wt", encoding="utf-8") as f:
        # Each response includes a "next_cursor"; it is empty on the last page.
        while params["cursor"]:
            data = get_with_retry(session, url, params)
            meta = data["meta"]
            if pages == 0:
                print(f"Total works matching filter: {meta['count']:,}")

            for work in data["results"]:
                if len(work.get("authorships") or []) >= AUTHORSHIP_CAP:
                    work = fetch_full_work(session, work["id"], api_key)
                    refetched += 1
                f.write(json.dumps(work, ensure_ascii=False) + "\n")

            n_works += len(data["results"])
            pages += 1
            cost += meta.get("cost_usd") or 0
            if pages % 50 == 0:
                print(f"  {n_works:,} works, {pages} pages, ${cost:.4f}, {time.time() - start:.0f}s")

            params["cursor"] = meta.get("next_cursor")
            if args.max_pages and pages >= args.max_pages:
                break

    size_mb = out.stat().st_size / 1e6
    print(f"Wrote {n_works:,} works to {out} ({size_mb:.1f} MB gzipped) "
          f"in {pages} list calls (+{refetched} single lookups for long author lists), "
          f"${cost:.4f}, {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
