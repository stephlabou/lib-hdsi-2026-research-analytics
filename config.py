"""
config.py -- the ONLY file you should need to edit.

Every other script imports its settings from here.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_dotenv(path):
    """Load simple KEY=VALUE entries without overriding existing variables."""
    if not path.exists():
        return

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if "=" not in entry:
            raise SystemExit(f"Invalid entry in {path.name} on line {line_number}: expected KEY=VALUE")

        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise SystemExit(f"Invalid entry in {path.name} on line {line_number}: missing variable name")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# 1. WHICH INSTITUTIONS?  (ROR IDs)
# ---------------------------------------------------------------------------
# Copy the RORs from the "organizational identifier spreadsheet" into this
# dictionary. Use the full URL form (https://ror.org/xxxxxxxxx).
# Replace every "TODO" before running 01_download.py.
#
# RORs taken from the org-identifier spreadsheet (UCSD = 'always'; the other
# three are 'yes - optional'). Delete a line to leave that organization out.
ROR_IDS = {
    "UC San Diego":                          "https://ror.org/0168r3w48",
    "San Diego Supercomputer Center (SDSC)": "https://ror.org/04mg3nk07",
    "Scripps Institution of Oceanography":   "https://ror.org/04v7hvq31",
    "UC San Diego Medical Center":           "https://ror.org/03aw5sn18",
}

# ---------------------------------------------------------------------------
# 2. WHICH YEARS?
# ---------------------------------------------------------------------------
YEAR_START = 2020
YEAR_END = 2026

# ---------------------------------------------------------------------------
# 3. WHERE DO FILES GO?
# ---------------------------------------------------------------------------
# Set the environment variable OPENALEX_RUN=test to keep a small test run
# completely separate from the full run (data/test/ instead of data/full/).
RUN_NAME = os.environ.get("OPENALEX_RUN", "full")
DATA_DIR = BASE_DIR / "data" / RUN_NAME
RAW_DIR = DATA_DIR / "raw_json"      # one JSON file per work (CLI output)
TABLE_DIR = DATA_DIR / "tables"      # flat CSV tables (02_flatten.py output)
FIG_DIR = DATA_DIR / "figures"       # charts and summary tables (03_analysis.py)

# ---------------------------------------------------------------------------
# 4. ANALYSIS CHOICES (see README "Questions to confirm")
# ---------------------------------------------------------------------------
# Which level of the OpenAlex topic hierarchy to use for "top 5 domains funded".
# "domain" has only 4 values, so the default is the more useful "field" (26
# values). Options: "domain", "field", "subfield", "topic"
FUNDER_TOPIC_LEVEL = "field"

# Include the US in the collaboration charts? (UCSD is itself in the US.)
INCLUDE_US_IN_COLLAB_CHART = False


def short_id(url):
    """'https://openalex.org/W123' -> 'W123'  (also works for ROR URLs)."""
    return url.rstrip("/").rsplit("/", 1)[-1] if url else ""


def ror_list():
    """Return the list of ROR URLs, stopping with a clear message if any
    are still marked TODO."""
    missing = [name for name, ror in ROR_IDS.items() if not ror or ror.startswith("TODO")]
    if missing:
        raise SystemExit(
            "config.py still has TODO placeholders for: " + ", ".join(missing)
            + "\n"
        )
    return list(ROR_IDS.values())
