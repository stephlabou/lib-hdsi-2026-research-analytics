"""Read OpenAlex's per-entity manifest.json from the public S3 snapshot."""

from __future__ import annotations

import json

import duckdb

from .config import S3_BUCKET, S3_REGION


def new_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{S3_REGION}';")
    return con


def list_files(con: duckdb.DuckDBPyConnection, entity: str) -> list[dict]:
    """Return the manifest's file list for one entity, each as
    {"url": ..., "content_length": ..., "record_count": ...}.
    """
    url = f"s3://{S3_BUCKET}/data/parquet/{entity}/manifest.json"
    raw = con.execute("SELECT content FROM read_text(?)", [url]).fetchone()[0]
    manifest = json.loads(raw)
    files = []
    for f in manifest["files"]:
        files.append(
            {
                "url": f["url"],
                "content_length": f["meta"]["content_length"],
                "record_count": f["meta"]["record_count"],
            }
        )
    return files
