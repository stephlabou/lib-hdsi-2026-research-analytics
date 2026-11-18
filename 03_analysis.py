"""
03_analysis.py -- exploratory statistics, tables and charts from the CSV tables
made by 02_flatten.py.

Outputs go to data/<run>/figures/ :
  summary.txt                       headline numbers
  works_by_year.csv
  citations_by_year.csv             citations per year + citations per unique researcher
  top_publishers_journals.csv       top 10 publishers, each with top 5 journals
  top_funders_topics.csv            top 10 funders, each with top 5 topic areas
  country_collaboration.csv
  fig_formats_by_year.png           articles vs books vs other, per year
  fig_open_access.png               OA status overall and by year
  fig_collab_countries.png          top collaborating countries (bar chart)
  fig_collab_network.png            country co-authorship network

Usage
  python 03_analysis.py
"""
import itertools
from collections import Counter

import matplotlib
matplotlib.use("Agg")                       # draw to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd

from config import (TABLE_DIR, FIG_DIR, YEAR_START, YEAR_END,
                    FUNDER_TOPIC_LEVEL, INCLUDE_US_IN_COLLAB_CHART)

FIG_DIR.mkdir(parents=True, exist_ok=True)
summary_lines = []


def say(text=""):
    """Print and also save to summary.txt."""
    print(text)
    summary_lines.append(text)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
works = pd.read_csv(TABLE_DIR / "works.csv", low_memory=False)
auth = pd.read_csv(TABLE_DIR / "authorships.csv", low_memory=False)
funders = pd.read_csv(TABLE_DIR / "funders.csv", low_memory=False)

works = works[works.publication_year.between(YEAR_START, YEAR_END)]
ucsd_auth = auth[auth.is_ucsd == 1].dropna(subset=["author_id"])

# A "journal article" = work type 'article' published in a source of type 'journal'
is_journal_article = (works.type == "article") & (works.source_type == "journal")

# ---------------------------------------------------------------------------
# Q1. How many works?
# ---------------------------------------------------------------------------
last5_start = YEAR_END - 4
works_by_year = works.groupby("publication_year").size().rename("works")
works_by_year.to_csv(FIG_DIR / "works_by_year.csv")
say(f"Total works {YEAR_START}-{YEAR_END}: {len(works):,}")
say(f"Total works in last 5 years ({last5_start}-{YEAR_END}): "
    f"{int((works.publication_year >= last5_start).sum()):,}")
say(f"  (note: {YEAR_END} is a partial year)")
say("Works by year:\n" + works_by_year.to_string())

# ---------------------------------------------------------------------------
# Q2. Unique UC San Diego researchers (author IDs on authorships at our RORs)
# ---------------------------------------------------------------------------
say(f"\nUnique UCSD author IDs, all years: {ucsd_auth.author_id.nunique():,}")
say("  (an OpenAlex author ID is a disambiguated profile; one real person can occasionally"
    " have more than one, or two people be merged)")
trunc = int(works.is_authors_truncated.sum())
say(f"Works with truncated author lists (>100 authors; later authors missing): {trunc:,}")

# ---------------------------------------------------------------------------
# Q3. Citations per year for journal articles, and per unique researcher
# ---------------------------------------------------------------------------
# "Year" = publication year. Citations are the lifetime total (cited_by_count) for
# articles published that year. Researchers = unique UCSD authors on those articles.
art = works[is_journal_article]
cites = art.groupby("publication_year").cited_by_count.sum().rename("total_citations")
art_authors = ucsd_auth.merge(art[["work_id", "publication_year"]], on="work_id")
researchers = art_authors.groupby("publication_year").author_id.nunique().rename("unique_ucsd_researchers")
cite_table = pd.concat([art.groupby("publication_year").size().rename("journal_articles"),
                        cites, researchers], axis=1)
cite_table["citations_per_researcher"] = (cite_table.total_citations
                                          / cite_table.unique_ucsd_researchers).round(2)
cite_table.to_csv(FIG_DIR / "citations_by_year.csv")
say("\nJournal-article citations by publication year:\n" + cite_table.to_string())

# ---------------------------------------------------------------------------
# Table: top 10 publishers, with top 5 journals each
# ---------------------------------------------------------------------------
pub_counts = works.dropna(subset=["publisher"]).groupby("publisher").size().nlargest(10)
rows = []
for rank, (pub, n_pub) in enumerate(pub_counts.items(), 1):
    journals = (works[(works.publisher == pub) & (works.source_type == "journal")]
                .groupby("source_name").size().nlargest(5))
    for j_rank, (journal, n_j) in enumerate(journals.items(), 1):
        rows.append({"publisher_rank": rank, "publisher": pub, "publisher_works": n_pub,
                     "journal_rank": j_rank, "journal": journal, "journal_works": n_j})
    if journals.empty:   # e.g. a repository publisher with no journals
        rows.append({"publisher_rank": rank, "publisher": pub, "publisher_works": n_pub})
pd.DataFrame(rows).to_csv(FIG_DIR / "top_publishers_journals.csv", index=False)
say("\nTop 10 publishers (works):\n" + pub_counts.to_string())

# ---------------------------------------------------------------------------
# Table: top 10 funders, with top 5 topic areas each
# ---------------------------------------------------------------------------
level_col = f"primary_topic_{FUNDER_TOPIC_LEVEL}" if FUNDER_TOPIC_LEVEL != "topic" else "primary_topic"
fw = (funders.dropna(subset=["funder"]).drop_duplicates(["work_id", "funder"])
      .merge(works[["work_id", level_col]], on="work_id"))
fund_counts = fw.groupby("funder").size().nlargest(10)
rows = []
for rank, (fname, n_f) in enumerate(fund_counts.items(), 1):
    areas = fw[fw.funder == fname].dropna(subset=[level_col]).groupby(level_col).size().nlargest(5)
    for a_rank, (area, n_a) in enumerate(areas.items(), 1):
        rows.append({"funder_rank": rank, "funder": fname, "funder_works": n_f,
                     "area_rank": a_rank, f"topic_{FUNDER_TOPIC_LEVEL}": area, "area_works": n_a})
pd.DataFrame(rows).to_csv(FIG_DIR / "top_funders_topics.csv", index=False)
say("\nTop 10 funders (works):\n" + fund_counts.to_string())
say(f"Works with at least one funder listed: {works.work_id.isin(funders.work_id).mean():.1%}")

# ---------------------------------------------------------------------------
# Chart: article vs book vs other, by year
# ---------------------------------------------------------------------------
def format_group(t):
    if t == "article":
        return "Journal article"
    if t in ("book", "book-chapter"):
        return "Book / chapter"
    return "Other"

fmt = works.assign(fmt=works.type.map(format_group)).groupby(["publication_year", "fmt"]).size().unstack(fill_value=0)
fmt = fmt.reindex(columns=["Journal article", "Book / chapter", "Other"], fill_value=0)
fig, ax = plt.subplots(figsize=(9, 5))
fmt.plot(kind="bar", stacked=True, ax=ax, color=["#1f77b4", "#ff7f0e", "#9aa0a6"])
ax.set_title("UC San Diego works by format and year")
ax.set_xlabel("Publication year"); ax.set_ylabel("Works")
plt.xticks(rotation=0); plt.tight_layout()
fig.savefig(FIG_DIR / "fig_formats_by_year.png", dpi=150); plt.close(fig)
fmt.to_csv(FIG_DIR / "formats_by_year.csv")

# ---------------------------------------------------------------------------
# Chart: open access
# ---------------------------------------------------------------------------
oa_order = ["diamond", "gold", "hybrid", "green", "bronze", "closed"]
oa_colors = {"diamond": "#17becf", "gold": "#e6b800", "hybrid": "#ff7f0e",
             "green": "#2ca02c", "bronze": "#a0522d", "closed": "#9aa0a6"}
oa_total = works.oa_status.value_counts().reindex(oa_order, fill_value=0)
oa_year = works.groupby(["publication_year", "oa_status"]).size().unstack(fill_value=0).reindex(columns=oa_order, fill_value=0)
oa_year_pct = oa_year.div(oa_year.sum(axis=1), axis=0) * 100
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
a1.bar(oa_total.index, oa_total.values, color=[oa_colors[k] for k in oa_total.index])
a1.set_title("Open access status (all works)"); a1.set_ylabel("Works")
oa_year_pct.plot(kind="bar", stacked=True, ax=a2, color=[oa_colors[k] for k in oa_order])
a2.set_title("Open access status by year (% of works)"); a2.set_xlabel("Publication year")
a2.set_ylabel("%"); plt.setp(a2.get_xticklabels(), rotation=0)
plt.tight_layout(); fig.savefig(FIG_DIR / "fig_open_access.png", dpi=150); plt.close(fig)
oa_year.to_csv(FIG_DIR / "open_access_by_year.csv")
say(f"\nOpen access: {works.is_oa.mean():.1%} of works are OA\n" + oa_total.to_string())

# ---------------------------------------------------------------------------
# Collaboration: which countries appear on works alongside UCSD authors?
# ---------------------------------------------------------------------------
ucsd_works = set(ucsd_auth.work_id)
others = auth[auth.work_id.isin(ucsd_works) & (auth.is_ucsd == 0)].dropna(subset=["institution_country_code"])
countries_per_work = others.groupby("work_id").institution_country_code.agg(lambda s: sorted(set(s)))
country_counts = Counter(c for cs in countries_per_work for c in cs)
collab = pd.DataFrame(country_counts.most_common(), columns=["country_code", "works_with_ucsd"])
collab.to_csv(FIG_DIR / "country_collaboration.csv", index=False)
chart_data = collab if INCLUDE_US_IN_COLLAB_CHART else collab[collab.country_code != "US"]

top = chart_data.head(25).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 8))
ax.barh(top.country_code, top.works_with_ucsd, color="#1f77b4")
ax.set_title("Top 25 countries co-authoring with UC San Diego\n(works with >=1 author affiliated in that country)")
ax.set_xlabel("Works"); plt.tight_layout()
fig.savefig(FIG_DIR / "fig_collab_countries.png", dpi=150); plt.close(fig)

# Network: UCSD hub + top-N countries; country-country edges = shared works.
try:
    import networkx as nx
    top_n = list(chart_data.head(30).country_code)
    G = nx.Graph()
    for c in top_n:
        G.add_edge("UCSD", c, weight=country_counts[c])
    pair_counts = Counter()
    for cs in countries_per_work:
        cs = [c for c in cs if c in top_n]
        pair_counts.update(itertools.combinations(cs, 2))
    for (a, b), n in pair_counts.items():
        G.add_edge(a, b, weight=n)
    pos = nx.spring_layout(G, seed=1, weight=None, k=0.9)
    sizes = [900 if n == "UCSD" else 80 + 600 * country_counts[n] / max(country_counts[top_n[0]], 1) for n in G]
    widths = [0.3 + 3 * d["weight"] / max(country_counts[top_n[0]], 1) for _, _, d in G.edges(data=True)]
    fig, ax = plt.subplots(figsize=(10, 10))
    nx.draw_networkx_edges(G, pos, width=widths, alpha=0.25, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, ax=ax,
                           node_color=["#c8102e" if n == "UCSD" else "#1f77b4" for n in G])
    nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)
    ax.set_title("UC San Diego country collaboration network\n(node size/edge width = number of works)")
    ax.axis("off"); plt.tight_layout()
    fig.savefig(FIG_DIR / "fig_collab_network.png", dpi=150); plt.close(fig)
except ImportError:
    say("\n(networkx not installed -- skipped network figure: pip install networkx)")

say(f"\nCountries appearing on UCSD works (incl. US): {len(collab)}")
(FIG_DIR / "summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")
print(f"\nAll outputs written to {FIG_DIR}")
