# MCP server for OpenAlex pull: design & sample workflow

## 1. Overview

The plan splits the work in two:

- **Our code** does the exact steps: build the query, get the results, retry on errors, save files. The same input always makes the same request.
- **The AI** picks which tool to use, fills in things like the year, and explains the results.

The AI never writes its own queries. This matters because our different methods give different results from day to day. If the query also changed each time, we could not tell if the data changed or the query changed.

- **The query is fixed, the results are not.** OpenAlex updates its data, so the same query can return different counts on different days. Fixing the query removes one cause of differences. It does not remove all of them.
- **When MCP helps.** For fixed queries, a plain script or command-line tool is already repeatable. MCP adds value when someone wants to ask in plain language ("how many UCSD papers in 2025, by type?") and have the AI pick the right call. That is why the logic lives in plain functions, and MCP is a thin layer on top. If MCP turns out to be unhelpful, the functions and command line still work.

## 2. Architecture

All the real work is in plain Python functions. The MCP server and a command-line tool both just call those functions. We add them as new files in the existing `openalex_ucsd` package (on a new branch), so they share the same config, the same ROR spreadsheet loader and the same `data/` folder as the S3 code.

```
            AI app
              |  MCP
        mcp_server.py (thin wrappers)         api_cli.py (command line)
              \                                /
                    api.py (all the logic)
                              |
              OpenAlex API + ROR spreadsheet (config.py)
```

Why build it this way:

- Anyone can run and test the code without an AI app.
- Big downloads can run from the command line, outside the chat.
- The AI path and the command-line path always send the same query.

New and existing files:

```
src/openalex_ucsd/
  config.py        # existing: ROR loader, DATA_DIR
  extract.py       # existing: S3 snapshot code
  api.py           # NEW: all the API logic
  mcp_server.py    # NEW: MCP tools that call api.py
  api_cli.py       # NEW: command line that calls api.py
data/api/works_2025/
  page_00001.jsonl.gz, page_00002.jsonl.gz, ...
  state.json       # progress, used to resume
  works_2025.manifest.json   # written when the download is finished
```

Rules:

1. Each tool does one fixed kind of request.
2. Each result shows the exact filter that was used.
3. Download tools save to files and return the folder, page count and row count, not the data.
4. Each finished download has an info file (manifest): filter, year, time of download, row count.
5. The API key comes from an environment variable, never from the AI.
6. Big downloads check how much budget is left, and can stop and continue later without losing or repeating data.
7. Each page is saved as its own file, so a crash can only affect one page.

## 3. Tool definitions and deterministic tasks

| Tool | You give it | What it does | You get back |
|---|---|---|---|
| `check_rate_limit` | nothing | asks OpenAlex how much budget is left | budget left |
| `count_works` | year | asks for 1 result and reads the total | count and filter |
| `works_by_type` | year | groups results by type (article, book, etc.) | count per type |
| `download_works` | year, optional page limit | saves results page by page; continues if run again | status, folder, pages, rows |
| `get_work` | work ID | fetches one full record | one record |

Always count first, then download. That way you know the size before you start.

`download_works` has a status:

- `in_progress`: it hit the page limit. Call it again to continue.
- `stopped_low_budget`: the daily budget is almost gone. Try again later.
- `done`: finished, and the info file is written.

Through MCP the page limit defaults to 20 per call, so no single tool call runs for too long. The AI just calls the tool again until the status is `done`. The command line has no limit by default.

## 4. OpenAlex API constraints

- You need an API key. It is free. Make an account at openalex.org and copy the key from `openalex.org/settings/api`.
- There is a daily budget. A free key gets about $1 per day. Fetching one record by ID is free. Searches cost money from the budget.
- You can ask the API how much budget is left at `/rate-limit`.
- One filter can list up to 100 values joined by `|`. That is enough for our ROR list.
- For big downloads, use a cursor (`cursor=*`) to move through pages.
- Search results may cut off the author list on papers with a huge number of authors. For those, fetch the paper by ID with `get_work`.
- A 429 error can mean "too fast" or "budget used up". Retrying helps with the first, not the second.

## 5. Reference implementation (sketch)

### api.py (query logic)

```python
import gzip, json, os, time
from datetime import datetime, timezone

import requests

from .config import DATA_DIR, load_rors

API = "https://api.openalex.org"
OUT = DATA_DIR / "api"


def _get(path, **params):
    params["api_key"] = os.environ["OPENALEX_API_KEY"]
    for attempt in range(5):
        r = requests.get(f"{API}/{path}", params=params, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)   # wait longer each retry
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(
        f"OpenAlex kept failing with status {r.status_code}. "
        "If it is 429, the daily budget may be used up."
    )


def _write_json(path, obj):
    # Write to a temp file, then rename, so a crash never leaves a half-written file
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def build_filter(year):
    rors = "|".join(load_rors())   # same ROR list as the S3 code
    return f"authorships.institutions.ror:{rors},publication_year:{year}"


def rate_limit():
    return _get("rate-limit")


def _budget_left():
    try:
        # check the field name against the /rate-limit docs
        return rate_limit()["rate_limit"]["daily_remaining_usd"]
    except (KeyError, RuntimeError, requests.RequestException):
        return None   # cannot tell, so do not block the download


def count_works(year):
    f = build_filter(year)
    data = _get("works", filter=f, per_page=1)
    return {"year": year, "count": data["meta"]["count"], "filter": f}


def works_by_type(year):
    f = build_filter(year)
    data = _get("works", filter=f, group_by="type")
    return {"year": year, "filter": f,
            "groups": [{"type": g["key_display_name"], "count": g["count"]}
                       for g in data["group_by"]]}


def get_work(work_id):
    return _get(f"works/{work_id}")


def download_works(year, max_pages=None, min_budget_usd=0.10):
    f = build_filter(year)
    folder = OUT / f"works_{year}"
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "state.json"

    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["filter"] != f:
            raise RuntimeError(
                "Saved progress used a different filter "
                "(different RORs?). Delete the folder to start over."
            )
    else:
        state = {"filter": f, "next_cursor": "*", "pages_done": 0,
                 "rows": 0, "done": False}

    def result(status, **extra):
        return {"status": status, "folder": str(folder), "year": year,
                "pages": state["pages_done"], "rows": state["rows"], **extra}

    if state["done"]:
        return result("done")

    pages_this_call = 0
    while state["next_cursor"]:
        if max_pages and pages_this_call >= max_pages:
            return result("in_progress")          # call again to continue
        if pages_this_call % 50 == 0:
            left = _budget_left()
            if left is not None and left < min_budget_usd:
                return result("stopped_low_budget", remaining_usd=left)

        data = _get("works", filter=f, per_page=200, cursor=state["next_cursor"])
        n = state["pages_done"] + 1
        page = folder / f"page_{n:05d}.jsonl.gz"
        tmp = folder / f"page_{n:05d}.tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for w in data["results"]:
                fh.write(json.dumps(w) + "\n")
        os.replace(tmp, page)                     # page file is complete

        state["rows"] += len(data["results"])
        state["pages_done"] = n
        state["next_cursor"] = data["meta"].get("next_cursor")
        _write_json(state_path, state)            # only now record progress
        pages_this_call += 1

    state["done"] = True
    _write_json(state_path, state)
    manifest = {"year": year, "filter": f, "pages": state["pages_done"],
                "rows": state["rows"],
                "retrieved_utc": datetime.now(timezone.utc).isoformat()}
    _write_json(folder / f"works_{year}.manifest.json", manifest)
    return result("done")
```

How the resume works: a page file is saved first, and progress (`state.json`) is updated after. If the program dies between the two, the next run fetches that same page again and overwrites the same file name. Nothing is lost and nothing is duplicated. Cursors may expire after a long pause (**check**). If that happens, delete the folder and start again.

### mcp_server.py (MCP wrapper)

```python
from mcp.server.fastmcp import FastMCP
from . import api

mcp = FastMCP("openalex-ucsd")


@mcp.tool()
def check_rate_limit() -> dict:
    """How much OpenAlex API budget is left today."""
    return api.rate_limit()


@mcp.tool()
def count_works(year: int) -> dict:
    """Count UCSD works published in a given year."""
    return api.count_works(year)


@mcp.tool()
def works_by_type(year: int) -> dict:
    """UCSD works in a year, grouped by type."""
    return api.works_by_type(year)


@mcp.tool()
def download_works(year: int, max_pages: int = 20) -> dict:
    """Download UCSD works for one year to files, up to max_pages pages per call.
    If the status is 'in_progress', call this tool again to continue."""
    return api.download_works(year, max_pages)


@mcp.tool()
def get_work(work_id: str) -> dict:
    """Get one full paper record by OpenAlex ID (like W123456789)."""
    return api.get_work(work_id)


if __name__ == "__main__":
    mcp.run()
```

### api_cli.py (command-line interface)

```python
import argparse, json
from . import api


def main():
    p = argparse.ArgumentParser(prog="openalex-api")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("budget")
    for name in ("count", "by-type", "download"):
        s = sub.add_parser(name)
        s.add_argument("--year", type=int, required=True)
        if name == "download":
            s.add_argument("--max-pages", type=int, default=None)
    args = p.parse_args()

    run = {
        "budget": lambda: api.rate_limit(),
        "count": lambda: api.count_works(args.year),
        "by-type": lambda: api.works_by_type(args.year),
        "download": lambda: api.download_works(args.year, args.max_pages),
    }[args.cmd]
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
```

## 6. Setup instructions

1. Get a free OpenAlex API key and set it: `export OPENALEX_API_KEY=...`
2. Test the query by hand first. If this fails, nothing else will work:
   ```
   curl "https://api.openalex.org/works?filter=authorships.institutions.ror:https://ror.org/0168r3w48,publication_year:2025&per_page=1&select=id&api_key=$OPENALEX_API_KEY"
   ```
   Look for a sensible number in `meta.count`. Then try several RORs joined with `|`. If the URL-style ROR does not work in the filter, try the institution ID filter instead.
3. In the existing repo, make a new branch and add the packages: `uv add "mcp[cli]" requests`.
4. Make sure `Bibliometrics - Organizational identifiers.xlsx` is at the repo root, like in the S3 README.
5. Add `api.py`, `mcp_server.py` and `api_cli.py` under `src/openalex_ucsd/`.
6. Test the plain code first, with no AI: `uv run python -m openalex_ucsd.api_cli budget`, then `... count --year 2025`, then `... by-type --year 2025`, then `... download --year 2025 --max-pages 2`.
7. Test the MCP part with the inspector: `uv run mcp dev src/openalex_ucsd/mcp_server.py`. Call each tool with 2025 and compare the results to the command line.
8. Add it to Claude Desktop in `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "openalex-ucsd": {
         "command": "uv",
         "args": ["--directory", "/FULL/PATH/TO/REPO", "run", "python", "-m", "openalex_ucsd.mcp_server"],
         "env": { "OPENALEX_API_KEY": "YOUR_KEY" }
       }
     }
   }
   ```
   For Claude Code: `claude mcp add openalex-ucsd -- uv --directory /FULL/PATH/TO/REPO run python -m openalex_ucsd.mcp_server`.
9. Restart the app and ask it what tools it has.

## 7. Sample workflow: UCSD works for a single year (2025)

Ask the AI, and it should use these tools:

1. "How much API budget do I have left?" uses `check_rate_limit`.
2. "How many UCSD works were published in 2025?" uses `count_works`.
3. "Break that down by type." uses `works_by_type`.
4. "Download them." uses `download_works`. It may need to call it several times until the status is `done`. The files end up in `data/api/works_2025/`.
5. Give the page files to the same flatten step the other approaches use (read all `page_*.jsonl.gz` files in the folder). When flattening, drop duplicate work IDs as a safety check.

Without an AI, run the same steps from the command line: `budget`, `count --year 2025`, `by-type --year 2025`, `download --year 2025`. For big downloads, use the command line and use the chat only for the count and the summary.

How to know it worked:

- The row count in the info file matches the count from step 2. Small gaps can happen if OpenAlex updates in between, so compare the times.
- The filter in the info file matches the RORs in the spreadsheet.
- The AI path and the command-line path give the same filter and count.
- Stop a download partway (for example with Ctrl+C or by killing the process), run it again, and check that it finishes with the same row count and no duplicate work IDs.
- Run `count_works` for the same year on two different days and write down both counts. This shows how much the API changes by itself.
- Compare the 2025 count to the S3 results for the same year, once someone has finished that extraction. We do not know yet why counts differ, so write the gap down instead of assuming it is small noise.

## 8. Existing OpenAlex MCP servers and client libraries

| Server | What it does |
|---|---|
| Apify `dltik/mcp-server-openalex` | 8 tools, you pay per call |
| `dgitj` (mcp.so) | Search papers by topic or author |
| `hbiaou` (mcp.so) | One search endpoint |
| `alex-mcp` (drAbreu) | Matches authors and builds researcher profiles |

From their descriptions, none of these filter by institution ROR and year, save to files, resume, and record what query was used. That is why this document builds our own. `alex-mcp` might help later with the faculty citation task (**check** that it works with the new API key rule).

The PyAlex library or OpenAlex's own command-line tool could replace the request code in `api.py`. Check how they handle retries and resuming first.
