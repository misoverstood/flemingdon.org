#!/usr/bin/env python3
"""
flemingdon.org daily build.

Reads entries from Airtable, picks one at random without repeating until the
list is exhausted, then writes item.json for the static front end.

Env:
  AIRTABLE_TOKEN  personal access token, data.records:read
"""

import json
import os
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AIRTABLE_BASE = "appRpN1mY1eO7TavS"
AIRTABLE_TABLE = "tbl7soJVlsYxqAjBa"
AIRTABLE_API = "https://api.airtable.com/v0"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ITEM_FILE = ROOT / "item.json"
USED_FILE = DATA_DIR / "used.json"
CACHE_FILE = DATA_DIR / "entries-cache.json"


def log(msg):
    print(msg, flush=True)


def read_json(path, default):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def fetch_entries(token):
    """Pull every record from the entries table, following pagination."""
    records = []
    offset = None

    while True:
        params = {"pageSize": "100"}
        if offset:
            params["offset"] = offset

        url = "{}/{}/{}?{}".format(
            AIRTABLE_API,
            AIRTABLE_BASE,
            AIRTABLE_TABLE,
            urllib.parse.urlencode(params),
        )
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})

        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)

        records.extend(payload.get("records", []))
        offset = payload.get("offset")
        if not offset:
            break

    return records


def normalise(record):
    f = record.get("fields", {})
    return {
        "id": record.get("id"),
        "text": (f.get("text") or "").strip(),
        "type": (f.get("type") or "").strip().lower(),
        "attribution": (f.get("attribution") or "").strip(),
        "source": (f.get("source") or "").strip(),
        "year": f.get("year"),
        "genius_id": (f.get("genius_id") or "").strip(),
        "tmdb_id": (f.get("tmdb_id") or "").strip(),
        "wiki_title": (f.get("wiki_title") or "").strip(),
        "openlibrary_id": (f.get("openlibrary_id") or "").strip(),
        "note": (f.get("note") or "").strip(),
        "skip": bool(f.get("skip")),
    }


def eligible(entries):
    live, blank, skipped = [], 0, 0
    for e in entries:
        if not e["text"]:
            blank += 1
        elif e["skip"]:
            skipped += 1
        else:
            live.append(e)
    log("entries: {} live, {} skipped, {} blank".format(len(live), skipped, blank))
    return live


def pick(live, used):
    """Random with no repeats. When the pool empties, reset but never repeat
    yesterday's entry two days running."""
    ids = {e["id"] for e in live}
    used = [rid for rid in used if rid in ids]
    last = used[-1] if used else None

    pool = [e for e in live if e["id"] not in used]
    if not pool:
        log("pool exhausted, resetting")
        used = []
        pool = [e for e in live if e["id"] != last] or list(live)

    choice = random.choice(pool)
    used.append(choice["id"])
    return choice, used


def main():
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()

    entries = None
    if token:
        try:
            raw = fetch_entries(token)
            entries = [normalise(r) for r in raw]
            write_json(CACHE_FILE, entries)
            log("fetched {} records from Airtable".format(len(entries)))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as err:
            log("Airtable fetch failed: {}".format(err))
    else:
        log("AIRTABLE_TOKEN not set")

    if entries is None:
        entries = read_json(CACHE_FILE, [])
        if not entries:
            log("no cache to fall back on, aborting")
            return 1
        log("using cached copy of {} records".format(len(entries)))

    live = eligible(entries)
    if not live:
        log("nothing eligible to publish, aborting")
        return 1

    choice, used = pick(live, read_json(USED_FILE, []))

    item = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": choice["id"],
        "text": choice["text"],
        "type": choice["type"],
        "attribution": choice["attribution"],
        "source": choice["source"],
        "year": choice["year"],
        "note": choice["note"],
        "expansion": None,
    }

    write_json(ITEM_FILE, item)
    write_json(USED_FILE, used)
    log("picked {} ({}): {}".format(choice["id"], choice["type"], choice["text"][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())