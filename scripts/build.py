#!/usr/bin/env python3
"""
flemingdon.org daily build.

Reads entries from Airtable, picks one at random without repeating until the
list is exhausted, enriches it from the API matching its type, then writes
item.json for the static front end.

Expansion sources by type:
  lyric     Genius   annotation on the matching lyric fragment, plus song meta
  dialogue  TMDB     film or show title, year, director/creator, overview
  quote     Wikipedia REST summary of the speaker
  passage   Open Library  work metadata and description

genius_id is optional: with it blank the build searches Genius using the
attribution and source fields and logs which song it settled on.

data/entries-cache.json is public (it lives in a public repo served by Pages),
so it holds live rows only. Skipped and blank rows never leave Airtable.

Env:
  AIRTABLE_TOKEN  personal access token, data.records:read  (required)
  GENIUS_TOKEN    Genius client access token                (lyrics)
  TMDB_TOKEN      TMDB API read access token (v4 bearer)    (dialogue)
"""

import json
import os
import random
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AIRTABLE_BASE = "appRpN1mY1eO7TavS"
AIRTABLE_TABLE = "tbl7soJVlsYxqAjBa"
AIRTABLE_API = "https://api.airtable.com/v0"

GENIUS_API = "https://api.genius.com"
TMDB_API = "https://api.themoviedb.org/3"
WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary"
OPENLIB_API = "https://openlibrary.org"

USER_AGENT = "flemingdon.org/1.0 (https://flemingdon.org)"
TIMEOUT = 30

# Genius hosts community translation and clean-edit pages that match searches
# but carry no useful annotations.
GENIUS_NOISE = ("translation", "traduc", "çeviri", "перевод", "übersetzung",
                "(clean", "romanization", "annotated")

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


def get_json(url, headers=None):
    """GET and parse JSON. Returns None on any failure rather than raising, so
    a dead API degrades the page instead of killing the build."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError) as err:
        log("  request failed: {} ({})".format(err, url.split("?")[0]))
        return None


# ---------------------------------------------------------------- Airtable

def fetch_entries(token):
    records = []
    offset = None

    while True:
        params = {"pageSize": "100"}
        if offset:
            params["offset"] = offset

        url = "{}/{}/{}?{}".format(
            AIRTABLE_API, AIRTABLE_BASE, AIRTABLE_TABLE,
            urllib.parse.urlencode(params),
        )
        payload = get_json(url, {"Authorization": "Bearer " + token})
        if payload is None:
            raise RuntimeError("Airtable request failed")

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
        "genius_id": str(f.get("genius_id") or "").strip(),
        "tmdb_id": str(f.get("tmdb_id") or "").strip(),
        "wiki_title": (f.get("wiki_title") or "").strip(),
        "openlibrary_id": (f.get("openlibrary_id") or "").strip(),
        "note": (f.get("note") or "").strip(),
        "skip": bool(f.get("skip")),
    }


# ----------------------------------------------------------------- picking

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


# -------------------------------------------------------------- enrichment

def flatten(text):
    """Lowercase, strip accents, normalise smart punctuation and whitespace.
    Genius uses curly apostrophes, Airtable rows use straight ones."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", " ").replace("\u2013", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def paragraphs(text):
    """Split a body into clean paragraphs."""
    if not text:
        return []
    parts = re.split(r"\n\s*\n|\n", text)
    return [p.strip() for p in parts if p.strip()]


def tidy(text):
    """Strip markdown links, bare URLs and emphasis marks from API prose.

    Genius annotations and Open Library descriptions are community-edited and
    routinely carry raw links, which would render as unclickable text.
    """
    if not text:
        return ""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)   # [label](url) -> label
    text = re.sub(r"<[^>]+>", "", text)                    # stray html
    text = re.sub(r"https?://\S+", "", text)               # bare urls
    text = re.sub(r"\S+\.(?:com|org|net|be)/\S*", "", text)  # schemeless links
    text = re.sub(r"[*_`]{1,3}", "", text)                 # emphasis marks
    text = re.sub(r"[ \t]{2,}", " ", text)                 # collapsed gaps
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)           # orphaned punctuation
    return text.strip(" \t-–—")


def clean_paragraphs(text, limit=None):
    """Split, tidy, and drop anything that was only a link or is too short to
    be a sentence — Genius leaves orphaned attributions like '– Paul Simon'."""
    out = []
    for para in paragraphs(text):
        para = tidy(para)
        if len(para) < 25:
            continue
        out.append(para)
    return out[:limit] if limit else out


def strip_markdown(text):
    """Open Library descriptions also carry editorial cross-reference blocks."""
    if not text:
        return ""

    for marker in ("----", "Also contained in:", "Contained in:",
                   "Source title:", "Includes:"):
        i = text.find(marker)
        if i != -1:
            text = text[:i]

    return text


def find_genius_song(entry, auth):
    """Resolve a song id from attribution + source when genius_id is blank.

    Returns the id as a string, or None. Every decision is logged so a wrong
    match is visible in the daily run rather than silently published.
    """
    terms = " ".join(p for p in (entry["attribution"], entry["source"]) if p).strip()
    if not terms:
        log("  no genius_id, and no attribution/source to search on")
        return None

    data = get_json(
        "{}/search?q={}".format(GENIUS_API, urllib.parse.quote(terms)), auth
    )
    if not data:
        return None

    hits = data.get("response", {}).get("hits", [])
    artist = flatten(entry["attribution"])
    title = flatten(entry["source"])

    best = None
    for hit in hits:
        r = hit.get("result", {}) or {}
        full = r.get("full_title") or r.get("title") or ""
        if any(n in full.lower() for n in GENIUS_NOISE):
            continue

        score = 0
        if title and title in flatten(r.get("title")):
            score += 2
        if artist and artist in flatten((r.get("primary_artist") or {}).get("name")):
            score += 2
        # Genius orders by relevance, so keep that as the tiebreaker.
        if best is None or score > best[0]:
            best = (score, r)

    if not best or best[0] == 0:
        log("  genius search for '{}' found nothing convincing".format(terms))
        return None

    r = best[1]
    log("  no genius_id, matched by search: {} (id {})".format(
        r.get("full_title"), r.get("id")))
    return str(r.get("id"))


def enrich_lyric(entry, token):
    if not token:
        log("  GENIUS_TOKEN not set, skipping lyric enrichment")
        return None

    auth = {"Authorization": "Bearer " + token}
    song_id = entry["genius_id"] or find_genius_song(entry, auth)
    if not song_id:
        return None

    song = get_json("{}/songs/{}?text_format=plain".format(GENIUS_API, song_id), auth)
    meta = {}
    if song:
        s = song.get("response", {}).get("song", {}) or {}
        album = (s.get("album") or {}).get("name")
        producers = [a.get("name") for a in (s.get("producer_artists") or []) if a.get("name")]
        writers = [a.get("name") for a in (s.get("writer_artists") or []) if a.get("name")]
        meta = {
            "title": s.get("title"),
            "artist": (s.get("primary_artist") or {}).get("name"),
            "album": album,
            "released": s.get("release_date_for_display"),
            "producers": producers[:4],
            "writers": writers[:4],
            "url": s.get("url"),
        }

    refs = get_json(
        "{}/referents?song_id={}&text_format=plain&per_page=50".format(GENIUS_API, song_id),
        auth,
    )

    body = None
    target = flatten(entry["text"])
    if refs:
        best = None
        for ref in refs.get("response", {}).get("referents", []):
            frag = flatten(ref.get("fragment"))
            if not frag or not ref.get("annotations"):
                continue
            if target and (target in frag or frag in target):
                score = abs(len(frag) - len(target))
                if best is None or score < best[0]:
                    best = (score, ref)
        if best:
            plain = (best[1]["annotations"][0].get("body") or {}).get("plain")
            body = clean_paragraphs(plain, limit=3)
            log("  matched annotation on: {}".format(best[1].get("fragment")))
        else:
            log("  no annotation matched this line")

    if not meta and not body:
        return None

    return {
        "source_name": "Genius",
        "source_url": meta.get("url"),
        "meta": meta,
        "body": body or [],
    }


def enrich_dialogue(entry, token):
    if not token:
        log("  TMDB_TOKEN not set, skipping dialogue enrichment")
        return None
    if not entry["tmdb_id"]:
        log("  no tmdb_id on this entry")
        return None

    auth = {"Authorization": "Bearer " + token}
    raw = entry["tmdb_id"].strip()

    # Accept "movie/550", "tv/1396" or a bare ID, defaulting to movie.
    if "/" in raw:
        kind, _, ident = raw.partition("/")
        kind = kind.strip().lower()
    else:
        kind, ident = "movie", raw
    if kind not in ("movie", "tv"):
        kind = "movie"

    data = get_json(
        "{}/{}/{}?append_to_response=credits".format(TMDB_API, kind, ident.strip()),
        auth,
    )
    if not data:
        return None

    if kind == "movie":
        title = data.get("title")
        released = data.get("release_date")
        crew = (data.get("credits") or {}).get("crew") or []
        leads = [c.get("name") for c in crew if c.get("job") == "Director"]
        lead_label = "Directed by"
    else:
        title = data.get("name")
        released = data.get("first_air_date")
        leads = [c.get("name") for c in (data.get("created_by") or []) if c.get("name")]
        lead_label = "Created by"

    meta = {
        "title": title,
        "released": (released or "")[:4] or None,
        "lead_label": lead_label,
        "leads": leads[:3],
        "genres": [g.get("name") for g in (data.get("genres") or [])][:3],
        "url": "https://www.themoviedb.org/{}/{}".format(kind, ident.strip()),
    }

    return {
        "source_name": "TMDB",
        "source_url": meta["url"],
        "meta": meta,
        "body": clean_paragraphs(data.get("overview")),
    }


def enrich_quote(entry):
    if not entry["wiki_title"]:
        log("  no wiki_title on this entry")
        return None

    title = urllib.parse.quote(entry["wiki_title"].replace(" ", "_"), safe="")
    data = get_json("{}/{}".format(WIKI_API, title))
    if not data or data.get("type", "").endswith("not_found"):
        return None

    meta = {
        "title": data.get("title"),
        "subtitle": data.get("description"),
        "url": (data.get("content_urls") or {}).get("desktop", {}).get("page"),
    }

    return {
        "source_name": "Wikipedia",
        "source_url": meta["url"],
        "meta": meta,
        "body": paragraphs(data.get("extract")),
    }


def enrich_passage(entry):
    ident = entry["openlibrary_id"]
    if not ident:
        log("  no openlibrary_id on this entry")
        return None

    ident = ident.strip().upper()
    if ident.startswith("OL") and ident.endswith("W"):
        data = get_json("{}/works/{}.json".format(OPENLIB_API, ident))
        url = "{}/works/{}".format(OPENLIB_API, ident)
    else:
        data = get_json("{}/isbn/{}.json".format(OPENLIB_API, ident))
        url = "{}/isbn/{}".format(OPENLIB_API, ident)
    if not data:
        return None

    description = data.get("description")
    if isinstance(description, dict):
        description = description.get("value")

    authors = []
    for a in data.get("authors") or []:
        key = (a.get("author") or a).get("key")
        if not key:
            continue
        person = get_json("{}{}.json".format(OPENLIB_API, key))
        if person and person.get("name"):
            authors.append(person["name"])

    meta = {
        "title": data.get("title"),
        "authors": authors[:3],
        "published": data.get("first_publish_date") or data.get("publish_date"),
        "subjects": (data.get("subjects") or [])[:4],
        "url": url,
    }

    return {
        "source_name": "Open Library",
        "source_url": url,
        "meta": meta,
        "body": clean_paragraphs(strip_markdown(description), limit=2),
    }


def enrich(entry):
    kind = entry["type"]
    log("enriching {} entry".format(kind or "untyped"))

    if kind == "lyric":
        return enrich_lyric(entry, os.environ.get("GENIUS_TOKEN", "").strip())
    if kind == "dialogue":
        return enrich_dialogue(entry, os.environ.get("TMDB_TOKEN", "").strip())
    if kind == "quote":
        return enrich_quote(entry)
    if kind == "passage":
        return enrich_passage(entry)

    log("  unknown type, no enrichment")
    return None


# -------------------------------------------------------------------- main

def main():
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()

    entries = None
    fresh = False
    if token:
        try:
            entries = [normalise(r) for r in fetch_entries(token)]
            fresh = True
            log("fetched {} records from Airtable".format(len(entries)))
        except RuntimeError as err:
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

    # The cache is public, so it only ever holds rows that are due to appear
    # on the site. Skipped and blank rows stay private in Airtable.
    if fresh:
        write_json(CACHE_FILE, live)

    choice, used = pick(live, read_json(USED_FILE, []))
    log("picked {} ({}): {}".format(choice["id"], choice["type"], choice["text"][:60]))

    item = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": choice["id"],
        "text": choice["text"],
        "type": choice["type"],
        "attribution": choice["attribution"],
        "source": choice["source"],
        "year": choice["year"],
        "note": choice["note"],
        "expansion": enrich(choice),
    }

    write_json(ITEM_FILE, item)
    write_json(USED_FILE, used)
    log("wrote item.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())