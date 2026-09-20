#!/usr/bin/env python3
"""
ID lookup helper for flemingdon.org.

Prints the exact value to paste into the matching Airtable column.

  python scripts/lookup.py genius ice cube it was a good day
  python scripts/lookup.py tmdb the godfather
  python scripts/lookup.py wiki mourid barghouti
  python scripts/lookup.py book nineteen eighty-four orwell

Env:
  GENIUS_TOKEN   required for `genius`
  TMDB_TOKEN     required for `tmdb`
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GENIUS_API = "https://api.genius.com"
TMDB_API = "https://api.themoviedb.org/3"
WIKI_API = "https://en.wikipedia.org/w/api.php"
OPENLIB_API = "https://openlibrary.org"

USER_AGENT = "flemingdon.org/1.0 (https://flemingdon.org)"
TIMEOUT = 30


def get_json(url, headers=None):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        sys.exit("HTTP {} from {}".format(err.code, url.split("?")[0]))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        sys.exit("request failed: {}".format(err))


def token(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit("{} is not set in this shell".format(name))
    if value.startswith("PASTE"):
        sys.exit("{} still holds the placeholder text".format(name))
    return value


def show(rows, column):
    """rows: list of (value_to_paste, description)"""
    if not rows:
        print("no matches")
        return
    width = max(len(r[0]) for r in rows)
    print()
    for i, (value, label) in enumerate(rows, 1):
        print("  {}. {}   {}".format(i, value.ljust(width), label))
    print("\n  -> paste into the '{}' column\n".format(column))


# ------------------------------------------------------------------ genius

def genius(query):
    data = get_json(
        "{}/search?q={}".format(GENIUS_API, urllib.parse.quote(query)),
        {"Authorization": "Bearer " + token("GENIUS_TOKEN")},
    )
    rows = []
    for hit in data.get("response", {}).get("hits", [])[:8]:
        r = hit.get("result", {})
        title = r.get("full_title") or r.get("title")
        # Translation pages clutter results; flag rather than hide them.
        if "Translation" in title or "Traduc" in title or "Çeviri" in title:
            title += "  [translation page]"
        rows.append((str(r.get("id")), title))
    show(rows, "genius_id")


# -------------------------------------------------------------------- tmdb

def tmdb(query):
    auth = {"Authorization": "Bearer " + token("TMDB_TOKEN")}
    q = urllib.parse.quote(query)
    rows = []

    movies = get_json("{}/search/movie?query={}".format(TMDB_API, q), auth)
    for r in movies.get("results", [])[:5]:
        year = (r.get("release_date") or "")[:4] or "----"
        rows.append((str(r.get("id")), "{}  ({}, film)".format(r.get("title"), year)))

    shows = get_json("{}/search/tv?query={}".format(TMDB_API, q), auth)
    for r in shows.get("results", [])[:5]:
        year = (r.get("first_air_date") or "")[:4] or "----"
        rows.append(("tv/" + str(r.get("id")),
                     "{}  ({}, series)".format(r.get("name"), year)))

    show(rows, "tmdb_id")


# -------------------------------------------------------------------- wiki

def wiki(query):
    params = urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": "8", "format": "json",
    })
    data = get_json("{}?{}".format(WIKI_API, params))
    rows = []
    for r in data.get("query", {}).get("search", []):
        snippet = r.get("snippet", "")
        for tag in ('<span class="searchmatch">', "</span>", "&quot;"):
            snippet = snippet.replace(tag, "")
        rows.append((r.get("title"), snippet[:70].strip()))
    show(rows, "wiki_title")


# -------------------------------------------------------------------- book

def book(query):
    params = urllib.parse.urlencode({"q": query, "limit": "8"})
    data = get_json("{}/search.json?{}".format(OPENLIB_API, params))
    rows = []
    for r in data.get("docs", []):
        key = (r.get("key") or "").replace("/works/", "")
        if not key:
            continue
        authors = ", ".join((r.get("author_name") or [])[:2]) or "unknown author"
        year = r.get("first_publish_year") or "----"
        rows.append((key, "{}  ({}, {})".format(r.get("title"), year, authors)))
    show(rows, "openlibrary_id")


COMMANDS = {"genius": genius, "tmdb": tmdb, "wiki": wiki, "book": book}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in COMMANDS:
        sys.exit(
            "usage: lookup.py <genius|tmdb|wiki|book> <search terms>\n"
            "  genius  -> genius_id        (needs GENIUS_TOKEN)\n"
            "  tmdb    -> tmdb_id          (needs TMDB_TOKEN)\n"
            "  wiki    -> wiki_title\n"
            "  book    -> openlibrary_id"
        )
    COMMANDS[sys.argv[1]](" ".join(sys.argv[2:]))


if __name__ == "__main__":
    main()