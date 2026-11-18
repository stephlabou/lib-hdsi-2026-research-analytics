"""Configuration for the UCSD OpenAlex extraction."""

from __future__ import annotations

from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
RORS_XLSX = ROOT / "Bibliometrics - Organizational identifiers.xlsx"
DATA_DIR = ROOT / "data"

PUBLICATION_YEAR_START = 2020
PUBLICATION_YEAR_END = 2026

S3_REGION = "us-east-1"
S3_BUCKET = "openalex"


def load_rors(xlsx_path: Path = RORS_XLSX) -> list[str]:
    """Read the organizational identifiers sheet and return full ROR URLs
    for every org whose "Query inclusion" column is not "no".
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["Sheet1"]

    rors: list[str] = []
    for row in ws.iter_rows(min_row=1, values_only=True):
        if not row or len(row) < 4:
            continue
        org, _grid, ror, inclusion = row[0], row[1], row[2], row[3]
        if not ror or not inclusion:
            continue
        if str(ror).strip().lower() == "ror":
            continue  # header row
        if str(inclusion).strip().lower() in ("no", "query inclusion"):
            continue
        rors.append(f"https://ror.org/{str(ror).strip()}")
    return rors
