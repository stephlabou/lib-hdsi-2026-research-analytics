"""How has the use of AI/ML methods in UC San Diego research grown (2020-2026), and in which fields?

What it does:
    Uses OpenAlex's title-and-abstract search to count UCSD works that mention
    AI/ML methods, then compares those counts with all UCSD works that have an
    abstract. Everything is done with group_by requests (OpenAlex returns the
    counts directly), so nothing large is downloaded and no API key is needed.

    Writes to ai_ml_methods/output/:
        by_year.csv               works mentioning each method, per year, and % of all works
        by_field.csv              AI/ML works and % per research field (all years)
        sample_matches.csv        20 random matching titles per method, to check by hand
        fig_share_by_year.png     line chart of % per year for each method
        fig_share_by_field.png    bar chart of the AI/ML share in each field

How to run (from the repository's top folder):
    pip install -r requirements.txt
    python ai_ml_methods/ai_ml_methods.py

Takes about 20 requests and under a minute.
"""

import csv
import os
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # save charts to files, no window needed
import matplotlib.pyplot as plt
import requests

API_URL = "https://api.openalex.org/works"
OUT_DIR = Path(__file__).resolve().parent / "output"

# Same four organizations and years as the data pull (OpenAlex institution IDs).
INSTITUTIONS = ["I36258959", "I181653535", "I150209017", "I4210132395"]
YEAR_START, YEAR_END = 2020, 2026

# Only works with an abstract can be searched fairly, so every count below,
# including the total we divide by, is limited to has_abstract:true.
BASE_FILTER = (
    f"authorships.institutions.id:{'|'.join(INSTITUTIONS)},"
    f"publication_year:{YEAR_START}-{YEAR_END},"
    "has_abstract:true"
)

# Search terms for each method. Quotes mean an exact phrase; OR means either.
# OpenAlex search ignores case and matches plurals ("neural networks").
METHODS = {
    "Machine learning": '"machine learning"',
    "Deep learning / neural networks": '"deep learning" OR "neural network"',
    "Large language models": '"large language model" OR ChatGPT OR GPT-4',
}
# "Any AI/ML" = mentions any of the terms above, or "artificial intelligence".
ANY_AI = "Any AI/ML"
METHODS[ANY_AI] = " OR ".join(list(METHODS.values()) + ['"artificial intelligence"'])

# Fields with fewer works than this are left out of the field chart,
# since a percentage of a few dozen works is not meaningful.
MIN_FIELD_WORKS = 500


def get(params):
    """Send one request to OpenAlex and return the JSON, retrying if it's busy."""
    api_key = os.environ.get("OPENALEX_API_KEY")  # optional
    if api_key:
        params = {**params, "api_key": api_key}
    for attempt in range(5):
        resp = requests.get(API_URL, params=params, timeout=60)
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)  # wait 1s, 2s, 4s, ... then try again
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def make_filter(search=None):
    """BASE_FILTER, plus a title-and-abstract search if one is given."""
    if search is None:
        return BASE_FILTER
    return f"{BASE_FILTER},title_and_abstract.search:{search}"


def counts_by(group, search=None):
    """Return {key: (display name, count)} for works grouped by one field."""
    groups = get({"filter": make_filter(search), "group_by": group})["group_by"]
    return {g["key"]: (g["key_display_name"], g["count"]) for g in groups}


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}")


def by_year():
    """Count works per year for each method and for all works with an abstract."""
    years = [str(y) for y in range(YEAR_START, YEAR_END + 1)]
    totals = counts_by("publication_year")
    rows = []
    for year in years:
        total = totals.get(year, ("", 0))[1]
        rows.append({"year": year, "all_works_with_abstract": total})
    for method, search in METHODS.items():
        counts = counts_by("publication_year", search)
        for row in rows:
            n = counts.get(row["year"], ("", 0))[1]
            row[method] = n
            row[f"{method} %"] = round(100 * n / row["all_works_with_abstract"], 2)
    write_csv(OUT_DIR / "by_year.csv", rows)
    return rows


def by_field():
    """AI/ML works and share for each research field (all years together)."""
    totals = counts_by("primary_topic.field.id")
    ai = counts_by("primary_topic.field.id", METHODS[ANY_AI])
    rows = []
    for key, (name, total) in totals.items():
        n = ai.get(key, ("", 0))[1]
        rows.append({"field": name, "all_works_with_abstract": total, "ai_ml_works": n,
                     "ai_ml_%": round(100 * n / total, 2)})
    rows.sort(key=lambda r: r["ai_ml_%"], reverse=True)
    write_csv(OUT_DIR / "by_field.csv", rows)
    return rows


def sample_matches(n=20):
    """Save a random sample of matching titles per method, to check the search by hand."""
    rows = []
    for method, search in METHODS.items():
        # seed makes the sample the same every run
        works = get({"filter": make_filter(search), "sample": n, "seed": 42, "per_page": n,
                     "select": "id,title,publication_year"})["results"]
        for w in works:
            rows.append({"method": method, "work_id": w["id"].rsplit("/", 1)[-1],
                         "year": w["publication_year"], "title": w["title"]})
    write_csv(OUT_DIR / "sample_matches.csv", rows)


def plot_by_year(rows):
    years = [r["year"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5))
    for method in METHODS:
        style = "-" if method == ANY_AI else "--"
        ax.plot(years, [r[f"{method} %"] for r in rows], style, marker="o", label=method)
    ax.set_title("UC San Diego works mentioning AI/ML methods in the title or abstract")
    ax.set_xlabel(f"Publication year ({YEAR_END} is partial)")
    ax.set_ylabel("% of UCSD works with an abstract")
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_share_by_year.png", dpi=150)
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'fig_share_by_year.png'}")


def plot_by_field(rows):
    rows = [r for r in rows if r["all_works_with_abstract"] >= MIN_FIELD_WORKS]
    rows = rows[::-1]  # largest share at the top of a horizontal bar chart
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh([r["field"] for r in rows], [r["ai_ml_%"] for r in rows])
    for i, r in enumerate(rows):
        ax.text(r["ai_ml_%"], i, f" {r['ai_ml_works']:,} works", va="center", fontsize=8)
    ax.set_title(f"Share of UCSD works mentioning AI/ML, by field ({YEAR_START}-{YEAR_END})")
    ax.set_xlabel("% of the field's works with an abstract")
    ax.set_xlim(right=max(r["ai_ml_%"] for r in rows) * 1.25)  # room for labels
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_share_by_field.png", dpi=150)
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'fig_share_by_field.png'}")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    year_rows = by_year()
    field_rows = by_field()
    sample_matches()
    plot_by_year(year_rows)
    plot_by_field(field_rows)

    # Short summary in the terminal
    print(f"\n{ANY_AI} share by year:")
    for r in year_rows:
        print(f"  {r['year']}: {r[ANY_AI]:>5,} of {r['all_works_with_abstract']:>6,} works ({r[ANY_AI + ' %']}%)")


if __name__ == "__main__":
    main()
