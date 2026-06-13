# Spotify Listening History Analyzer

A personal data project that takes my raw Spotify streaming history and builds
a fully enriched analytical dataset — loaded into PostgreSQL and visualized
in Power BI.

---

## Project Roadmap

### Phase 1 — Data Enrichment *(in progress)*
Enrich raw listening history JSON files with track metadata, audio features,
and genre tags from external APIs. Output: a clean enriched CSV/JSON ready
for loading.

### Phase 2 — ETL Pipeline & Schema
Design a PostgreSQL star schema and build a Python pipeline that loads both
the raw plays data and the enriched track data into the database.

### Phase 3 — Analysis & Dashboard
Write SQL analysis queries and build an interactive Power BI dashboard
covering listening patterns, genre evolution, skip behavior, and more.

---

## Data Source

Spotify's **Download Your Data** feature provides a JSON file per year of
listening history. Each record is one play event and contains:

| Field | Description |
|---|---|
| `ts` | Timestamp of the play (UTC) |
| `platform` | Device and OS |
| `ms_played` | Milliseconds actually listened |
| `conn_country` | Country at time of play |
| `master_metadata_track_name` | Track name |
| `master_metadata_album_artist_name` | Artist name |
| `master_metadata_album_album_name` | Album name |
| `spotify_track_uri` | Spotify URI (contains track ID) |
| `reason_start` | Why the track started (e.g. `trackdone`, `clickrow`) |
| `reason_end` | Why the track ended (e.g. `trackdone`, `fwdbtn`) |
| `shuffle` | Whether shuffle was on |
| `skipped` | Whether the track was skipped |
| `offline` | Whether played offline |
| `incognito_mode` | Whether private session was active |
| `episode_name` / `spotify_episode_uri` | Populated for podcasts (null for music) |

The `ms_played` and `reason_end` fields are the real engagement signal —
more honest than play counts since they capture whether a track was actually
listened to or immediately skipped.

---

## Phase 1 — Enrichment Pipeline

### Original Plan

The original enrichment design used three Spotify batch endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /tracks` | Fetch metadata for up to 50 tracks at once |
| `GET /audio-features` | Fetch danceability, energy, valence, tempo, etc. for up to 100 tracks |
| `GET /artists` | Fetch genre tags and popularity for up to 50 artists |

These endpoints would have made enriching 20k+ tracks fast, clean, and free.

### What Happened — Spotify API Changes

Midway through building the enrichment script, I discovered that Spotify had
made two major rounds of breaking changes to their Web API:

**November 27, 2024 — Audio features and related endpoints deprecated:**
Spotify announced that new applications would no longer have access to:

- `GET /audio-features/{id}` and `GET /audio-features` — danceability, energy, valence, tempo, key, mode, etc.
- `GET /audio-analysis/{id}` — per-segment beat/bar analysis
- `GET /recommendations` — genre and feature-seed recommendations
- `GET /artists/{id}/related-artists` — related artist discovery
- `GET /browse/featured-playlists`
- `GET /browse/categories/{id}/playlists`

Any app created after that date receives a `403 Forbidden` on all of the
above. There is no workaround, no waitlist, and as of mid-2026 Spotify has
not announced a replacement.

**February 2026 — Batch endpoints removed:**
A second wave of changes removed all batch lookup endpoints for apps in
developer mode:

- `GET /tracks` — batch track lookup removed (fetch individually via `GET /track/{id}`)
- `GET /artists` — batch artist lookup removed (fetch individually via `GET /artist/{id}`)
- `GET /albums` — batch album lookup removed
- `GET /artists/{id}/top-tracks` — removed
- `GET /browse/new-releases` — removed

The practical impact: what was 200 batch requests for 20k tracks became
20,000 individual requests — requiring threading to keep the runtime manageable.

### Solutions Considered

With audio features gone from the official Spotify API, I researched alternatives:

**1. Apple Music API**
Provides `tempo`, `key`, and `timeSignature` but is missing `danceability`,
`energy`, `valence`, and `acousticness` — more than half the fields needed.
Requires a paid Apple Developer subscription for production use.


**2. Essentia (build your own)**
Essentia is the open-source audio analysis toolkit that Spotify itself
originally used to generate these features. Can reproduce all the same
fields — but requires the actual audio files, which Spotify does not provide.
Ruled out: no audio files available.

**3. AcousticBrainz public dataset**
MusicBrainz released a public dump of ~7.5 million tracks with full audio
features before shutting the service down in July 2022. Entirely free, no
rate limits, same fields as Spotify. However the dataset is ~30GB compressed
and frozen at 2022 — no data for anything released after that.
Ruled out: download size is a problem due to a personal internet issue.

**4. Paid APIs (FreqBlog, Musicae, Cyanite)**
Several commercial services rebuilt the Spotify audio features endpoint.
FreqBlog offers a drop-in `GET /v1/audio-features/{spotify_id}` endpoint
from £0.17 per 1,000 requests with a free tier. Viable, but introduces a
paid dependency for a personal project.


**5. ReccoBeats**
A free community-built API that accepts a Spotify track ID and returns the
same audio feature fields Spotify used to provide — danceability, energy,
valence, tempo, loudness, acousticness, instrumentalness, speechiness,
liveness, key, mode, and time signature. No authentication required.
Reliability is reported as inconsistent, and the rate limit is undocumented.

### Decision

**ReccoBeats** was chosen as the audio features source for the following reasons:

- Free, no API key or account required
- Accepts the Spotify track ID directly — no separate lookup or matching step
- Returns the same field names and value ranges as the original Spotify endpoint
- For a personal overnight enrichment run, reliability is manageable: failed
  lookups are cached as null and skipped on retry rather than crashing the run
- Worst case: some tracks have null audio features, which is acceptable for
  personal analysis

The script uses a conservative rate — single-threaded with a 2-second sleep
between requests — since the rate limit is undocumented and being blocked
would require restarting from scratch. At that pace, 20k tracks takes roughly
11 hours, designed to run overnight.

**MusicBrainz** is retained as a separate pass for standardized genre tags,
which ReccoBeats does not provide.

### Final Enrichment Architecture

```
Pass 1    — Spotify API
              GET /track/{id}   → track metadata (name, duration, popularity, album)
              GET /artist/{id}  → artist metadata (genres, followers, popularity)
              Threaded (5 workers), cache in cache/spotify/

Pass 1.5  — ReccoBeats API
              GET /v1/track/{spotify_id}/audio-features
              → danceability, energy, valence, tempo, loudness, acousticness,
                instrumentalness, speechiness, liveness, key, mode, time_signature
              Single-threaded, 2s/req, cache in cache/reccobeats/

Pass 2    — MusicBrainz API
              Search by artist + track name → standardized genre tags
              Single-threaded, 1.1s/req (strictly enforced), cache in cache/musicbrainz/
```

All three passes are fully independent and resumable. Each has its own cache
directory. Re-running after a crash only fetches what has not been cached yet.

### Output Fields

| Field | Source |
|---|---|
| `track_id`, `track_uri` | Raw history |
| `track_name`, `duration_ms`, `popularity`, `explicit` | Spotify |
| `track_number`, `disc_number` | Spotify |
| `artist_id`, `artist_name`, `all_artist_names` | Spotify |
| `artist_popularity`, `artist_followers`, `spotify_genres` | Spotify |
| `album_id`, `album_name`, `album_release_date`, `album_type`, `album_total_tracks` | Spotify |
| `danceability`, `energy`, `valence`, `tempo`, `loudness` | ReccoBeats |
| `acousticness`, `instrumentalness`, `speechiness`, `liveness` | ReccoBeats |
| `key`, `mode`, `time_signature` | ReccoBeats |
| `mb_recording_id`, `mb_match_score`, `mb_tags`, `mb_artist_tags` | MusicBrainz |



## Phase 2 — ETL Pipeline & Schema *(planned)*

- Design PostgreSQL star schema: `fact_plays`, `dim_track`, `dim_artist`, `dim_album`, `dim_date`
- Parse and clean raw plays data: session derivation, timestamp casting, derived columns
- Load enriched tracks and plays into Postgres via SQLAlchemy
- Structured logging throughout

---

## Phase 3 — Analysis & Dashboard *(planned)*

Planned analysis angles:
- Listening hours by time of day and day of week
- Skip rate by artist and genre — `reason_end = fwdbtn` as the real skip signal
- Genre and mood evolution year over year
- Top artists by actual listening time (`ms_played`), not just play count
- New artist discovery rate per month
- Offline vs online listening patterns
- Session length distribution

Dashboard in Power BI using the PostgreSQL connection with DAX measures.

---

## Stack

| Layer | Tool |
|---|---|
| Enrichment | Python, spotipy, requests |
| Database | PostgreSQL |
| ETL | Python, pandas, SQLAlchemy |
| Visualization | Power BI |