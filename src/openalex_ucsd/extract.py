"""Extract UCSD-affiliated works from the OpenAlex public S3 snapshot.

Scans every file in the `works` entity's parquet manifest (anonymous access,
no AWS account needed) and writes out, as raw gzipped JSON Lines, the rows
whose authorships include one of our target RORs and whose publication_year
falls in the configured range. One output file per source manifest file, so
the job is resumable: files that already have a `.done` marker are skipped.
"""

from __future__ import annotations

import argparse
import sys
import time

from .config import DATA_DIR, PUBLICATION_YEAR_END, PUBLICATION_YEAR_START, load_rors
from .manifest import list_files, new_connection

ENTITY = "works"


def ror_filter_sql(rors: list[str]) -> str:
    ror_list = ", ".join(f"'{r}'" for r in rors)
    return (
        "EXISTS ("
        "SELECT 1 FROM UNNEST(authorships) AS t(a), UNNEST(a.institutions) AS u(inst) "
        f"WHERE inst.ror IN ({ror_list})"
        ")"
    )


def output_paths(out_dir, file_url: str) -> tuple:
    # e.g. s3://openalex/data/parquet/works/updated_date=2026-10-14/part_0000.parquet
    tail = file_url.split(f"/{ENTITY}/", 1)[1]  # updated_date=.../part_0000.parquet
    name = tail.replace("/", "__").removesuffix(".parquet")
    out_file = out_dir / f"{name}.jsonl.gz"
    done_marker = out_dir / f"{name}.done"
    return out_file, done_marker


def run(limit_files: int | None = None, row_limit: int | None = None) -> None:
    out_dir = DATA_DIR / "raw" / ENTITY
    out_dir.mkdir(parents=True, exist_ok=True)

    rors = load_rors()
    print(f"Matching {len(rors)} RORs: {rors}", file=sys.stderr)

    con = new_connection()
    con.execute("SET threads=16;")

    files = list_files(con, ENTITY)
    if limit_files:
        files = files[:limit_files]
    print(f"{len(files)} manifest files to process", file=sys.stderr)

    where = (
        f"publication_year BETWEEN {PUBLICATION_YEAR_START} AND {PUBLICATION_YEAR_END} "
        f"AND {ror_filter_sql(rors)}"
    )

    total_matched = 0
    for i, f in enumerate(files, 1):
        out_file, done_marker = output_paths(out_dir, f["url"])
        if done_marker.exists():
            continue

        inner = f"SELECT * FROM read_parquet('{f['url']}')"
        if row_limit:
            inner += f" LIMIT {row_limit}"

        sql = (
            f"COPY (SELECT * FROM ({inner}) WHERE {where}) "
            f"TO '{out_file}' (FORMAT JSON, COMPRESSION GZIP);"
        )

        start = time.monotonic()
        result = con.execute(sql).fetchone()
        matched = result[0] if result else 0
        elapsed = time.monotonic() - start
        total_matched += matched

        if matched == 0:
            out_file.unlink(missing_ok=True)
        done_marker.touch()

        print(
            f"[{i}/{len(files)}] {f['url'].rsplit('/', 1)[-1]} "
            f"matched={matched} total={total_matched} elapsed={elapsed:.1f}s",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-files", type=int, default=None, help="Only process the first N manifest files")
    parser.add_argument("--row-limit", type=int, default=None, help="Only scan the first N rows per file (testing)")
    args = parser.parse_args()
    run(limit_files=args.limit_files, row_limit=args.row_limit)


if __name__ == "__main__":
    main()
