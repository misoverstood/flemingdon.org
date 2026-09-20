# flemingdon.org

A one-page site showing a single line a day: a rap lyric, a line of film or TV
dialogue, a quote, or a passage from a book, laid out like a dictionary entry
and expanded with context pulled from whichever API suits that type.

Live at <https://flemingdon.org>. Started September 2026.

## How it works

Content lives in Airtable. Once a day a GitHub Action picks one entry at
random, fetches context for it, writes `item.json`, and commits it back to this
repo. The page is static HTML that reads that one file.

```text
Airtable (entries)
      |
      v
GitHub Action (daily 09:05 UTC)
  scripts/build.py
      |
      +--> Genius        lyric annotation + song metadata
      +--> TMDB          film/show title, year, director, overview
      +--> Wikipedia     summary of the speaker
      +--> Open Library  book metadata and description
      |
      v
  item.json  ->  committed to gh-pages  ->  index.html renders it
```

There is no build step and no server. A push to `gh-pages` is the deploy.

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | The entire front end: markup, CSS and JS in one file |
| `scripts/build.py` | Picks the day's entry and enriches it |
| `.github/workflows/daily.yml` | The daily cron |
| `item.json` | Today's entry. Written by the bot, read by the page |
| `data/used.json` | Which entries have been shown this cycle |
| `data/entries-cache.json` | Last good copy of the Airtable table, used if Airtable is unreachable |
| `CNAME` | Custom domain binding. Deleting it unbinds flemingdon.org |
| `favicon.*`, `apple-touch-icon.png`, `android-chrome-*.png` | Icon set: a quotation mark set in Fraunces |

## Airtable

Base `flemingdon`, table `entries`.
Base ID `appRpN1mY1eO7TavS`, table ID `tbl7soJVlsYxqAjBa`.

| Field | Type | Notes |
|---|---|---|
| `text` | Long text | The line itself. Line breaks are preserved |
| `type` | Single select | `lyric`, `dialogue`, `quote`, `passage`. Decides which API is called |
| `attribution` | Single line | Artist, character, speaker or author |
| `source` | Single line | Song, film, show or book. Wins over the API's own title |
| `year` | Number | Optional, used when the API has no date |
| `genius_id` | Single line | Optional override for lyrics |
| `tmdb_id` | Single line | Dialogue only. `238` for a film, `tv/1396` for a series |
| `wiki_title` | Single line | Quotes only. Exact Wikipedia page title |
| `openlibrary_id` | Single line | Passages only. Work ID like `OL1168083W`, or an ISBN |
| `note` | Long text | Your own gloss. Renders under the API context, darker |
| `skip` | Checkbox | Tick to retire an entry. Blank means live |

Adding an entry needs four fields: `text`, `type`, `attribution`, `source`.
Everything else is optional.

### Where the IDs come from

Three of the four are readable straight from the URL:

- TMDB: `themoviedb.org/movie/238` -> `238`; `themoviedb.org/tv/1396` -> `tv/1396`
- Open Library: `openlibrary.org/works/OL1168083W` -> `OL1168083W`
- Wikipedia: `en.wikipedia.org/wiki/Mourid_Barghouti` -> `Mourid Barghouti`

Genius song IDs appear nowhere in the page URL, so `build.py` searches Genius
using `attribution` and `source`, skipping translation and clean-edit pages,
and logs which song it matched. Fill `genius_id` only when that log shows a
wrong match.

## Selection

Random with no repeats until the list is exhausted, tracked in
`data/used.json`. When the pool empties it resets, excluding the most recent
entry so the same line never runs two days running. Rows added mid-cycle become
eligible immediately.

## Enrichment, per type

| Type | Source | What comes back |
|---|---|---|
| `lyric` | Genius | The annotation attached to the matching lyric fragment, plus album, release date, producers and writers. Not every line is annotated |
| `dialogue` | TMDB | Title, year, director or creator, genres, overview |
| `quote` | Wikipedia REST | One-line description and summary of the speaker |
| `passage` | Open Library | Title, authors, first publication, subjects, description |

Genius matching normalises curly apostrophes and accents, because Genius uses
typographic quotes and Airtable rows use straight ones.

Every API call returns `None` on failure rather than raising, so an outage
produces a page with the line and no context instead of no page at all. If
Airtable itself is unreachable the build falls back to
`data/entries-cache.json`.

## Credentials

Stored as GitHub repo secrets, nowhere else in this repo:

| Secret | Used for | Where to rotate |
|---|---|---|
| `AIRTABLE_TOKEN` | Reading the entries table | airtable.com/create/tokens, scope `data.records:read` |
| `GENIUS_TOKEN` | Lyric annotations | genius.com/api-clients, the Client Access Token |
| `TMDB_TOKEN` | Film and TV metadata | themoviedb.org/settings/api, the API Read Access Token |

The TMDB token is shared with the iseentit project, since TMDB issues one
credential per account. Regenerating it breaks both.

Open Library and Wikipedia need no credentials.

## Running it locally

```powershell
cd C:\Github\flemingdon.org
$env:AIRTABLE_TOKEN='...'; $env:GENIUS_TOKEN='...'; $env:TMDB_TOKEN='...'
python .\scripts\build.py
python -m http.server 8000   # then open http://localhost:8000
```

Opening `index.html` directly over `file://` will not work: the browser blocks
the `item.json` fetch. Use the local server.

## Deploying

```powershell
git pull --rebase; git add -A; git commit -m "message"; git push
```

Pull first: the daily bot commits to the same branch, so your local copy is
often behind. Pages rebuilds in under a minute. Hard-refresh with Ctrl+Shift+R,
since browsers cache the page aggressively.

To publish a new entry immediately rather than waiting for the cron, go to
Actions -> Daily entry -> Run workflow.

## Hosting

GitHub Pages from `gh-pages` at root, custom domain `flemingdon.org`, HTTPS
enforced. DNS is Cloudflare, free plan, with all web records set to **DNS
only**: proxying hides the origin from GitHub's certificate check and breaks
HTTPS.

| Record | Value |
|---|---|
| `flemingdon.org` A x 4 | 185.199.108.153, .109.153, .110.153, .111.153 |
| `www` CNAME | flemingdon.org |

Mailgun MX and TXT records also live on this zone and are unrelated to the site.

## Design

Fraunces for the entry text, Lato for metadata, both from Google Fonts. Warm
cream paper with a green accent; the palette flips with the OS dark mode
setting. Layout is centred and responsive, with no share button by design.

The type line, attribution, sense block and fact list mirror a dictionary entry
without the literal apparatus of pronunciation keys and part-of-speech
abbreviations, which stop being funny on a four-line poem.

## Notes and gotchas

- The cron is UTC and ignores daylight saving: 05:05 Toronto in summer, 04:05
  in winter. GitHub may delay scheduled runs under load.
- Genius sometimes files a track under a compilation rather than its album,
  which is why `source` from Airtable takes precedence.
- Open Library often lacks `first_publish_date`; the page falls back to the
  `year` field.
- All rendering goes through `textContent`, so third-party text cannot inject
  markup into the page.
- TMDB's terms require an attribution line, which renders only on `dialogue`
  days. Wikipedia and Genius are credited per entry in the footer.
