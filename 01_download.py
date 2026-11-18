"""
01_download.py -- download all UC San Diego works from OpenAlex with the
official OpenAlex command-line tool.

What it does
  1. Builds one OpenAlex filter from the ROR IDs and years in config.py.
  2. (Optional) asks the API how many works match, before downloading.
  3. Runs `openalex download`, which writes ONE JSON FILE PER WORK
     (e.g. W2741809807.json) into data/<run>/raw_json/.
  4. Prints how many files were downloaded and how big they are.

Setup (once)
  pip install openalex-official
  copy .env.example .env                    # then add your key to .env

Usage
  python 01_download.py --count-only      # just report how many works match
  OPENALEX_RUN=test python 01_download.py --test   # tiny 1-week sample (do this first!)
  python 01_download.py                   # the full download

The CLI checkpoints its progress, so if a download is interrupted you can
simply run the same command again and it resumes.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from config import (RAW_DIR, RUN_NAME, YEAR_START, YEAR_END, ror_list)


def build_filter(test=False):
    """Make the OpenAlex filter string.

    authorships.institutions.ror:A|B|C   -> any author affiliated with A OR B OR C
    publication_year:2020-2026           -> year range (inclusive)
    Comma = AND between different filters; pipe (|) = OR inside one filter.
    """
    rors = "|".join(ror_list())
    flt = f"authorships.institutions.ror:{rors},publication_year:{YEAR_START}-{YEAR_END}"
    if test:
        # Narrow to one week so the test finishes in seconds.
        flt += f",from_publication_date:{YEAR_END}-01-01,to_publication_date:{YEAR_END}-01-07"
    return flt


def count_matching_works(flt, api_key):
    """Ask the REST API for the number of matching works (one cheap request)."""
    params = urllib.parse.urlencode({"filter": flt, "per-page": 1, "api_key": api_key},
                                    safe=":|,/")
    url = "https://api.openalex.org/works?" + params
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)["meta"]["count"]


def folder_size(path):
    """Return (number of .json files, total bytes) for a folder."""
    n, total = 0, 0
    if path.exists():
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
                if entry.name.endswith(".json"):
                    n += 1
    return n, total


def human(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024 or unit == "TB":
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="download only 1 week of data (use with OPENALEX_RUN=test)")
    ap.add_argument("--count-only", action="store_true", help="only report how many works match; download nothing")
    ap.add_argument("--dry-run", action="store_true", help="print the command without running it")
    args = ap.parse_args()

    if args.test and RUN_NAME == "full":
        sys.exit("For --test, run:  OPENALEX_RUN=test python 01_download.py --test\n"
                 "(keeps the test files out of your full-run folder)")

    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key == "replace_with_your_openalex_api_key":
        api_key = None
    if not api_key and not args.dry_run:
        sys.exit("Set OPENALEX_API_KEY in .env or in your environment before running.")

    flt = build_filter(test=args.test)
    print("Filter:", flt)

    if args.count_only:
        print(f"Matching works: {count_matching_works(flt, api_key):,}")
        return

    if os.name == "nt":
        # openalex-official 0.3.3 uses Unix-only signal handlers on Windows.
        openalex_command = sys.executable
        openalex_prefix = [
            openalex_command,
            "-c",
            "import asyncio, runpy; "
            "asyncio.BaseEventLoop.add_signal_handler = lambda self, *args: None; "
            "asyncio.BaseEventLoop.remove_signal_handler = lambda self, *args: None; "
            "runpy.run_module('openalex_cli.cli', run_name='__main__')",
        ]
    else:
        openalex_command = shutil.which("openalex")
        if openalex_command is None:
            scripts_dir = Path(sys.executable).resolve().parent / "Scripts"
            candidate = scripts_dir / "openalex"
            if candidate.is_file():
                openalex_command = str(candidate)
        openalex_prefix = [openalex_command] if openalex_command else []

    if not openalex_prefix and not args.dry_run:
        sys.exit("The 'openalex' command was not found. Install it with:\n  pip install openalex-official")

    cmd = openalex_prefix + ["download", "--api-key", api_key or "YOUR_KEY",
           "--output", str(RAW_DIR), "--filter", flt, "--workers", "5"]
    display_cmd = cmd.copy()
    if "--api-key" in display_cmd:
        key_index = display_cmd.index("--api-key") + 1
        if key_index < len(display_cmd):
            display_cmd[key_index] = "***"
    print("Command:", " ".join(display_cmd))
    if args.dry_run:
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"openalex exited with code {result.returncode}. Re-run to resume from the checkpoint.")

    n, total = folder_size(RAW_DIR)
    print("\n=== Download size ===")
    print(f"JSON files : {n:,}")
    print(f"Total size : {human(total)}")
    if n:
        print(f"Average    : {human(total / n)} per work")


if __name__ == "__main__":
    main()
