"""Shared settings for the OpenAlex API scripts. Edit here to change the scope."""

# Same four organizations as the OQL approach (OpenAlex institution IDs).
INSTITUTIONS = {
    "University of California San Diego": "I36258959",
    "San Diego Supercomputer Center": "I181653535",
    "Scripps Institution of Oceanography": "I150209017",
    "University of California San Diego Medical Center": "I4210132395",
}

YEAR_START = 2020
YEAR_END = 2026

API_BASE = "https://api.openalex.org"

# The filter used by every script: works with an author at any of the
# institutions ("|" means OR) AND published in the year range ("," means AND).
WORKS_FILTER = (
    f"authorships.institutions.id:{'|'.join(INSTITUTIONS.values())},"
    f"publication_year:{YEAR_START}-{YEAR_END}"
)
