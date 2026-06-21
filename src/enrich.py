"""
enrich.py
Main enrichment pipeline — three sequential passes, all resumable overnight.

Pass 1  — Spotify API
  Fetches track metadata (name, duration, popularity, explicit, album, artists)
  and artist metadata (genres, followers, popularity).
  Threaded for speed. Cache in cache/spotify/.

Pass 1.5 — ReccoBeats API
  Fetches audio features per track (energy, valence, danceability, tempo, etc.)
  using the Spotify track ID. Single-threaded at 2s/req — safe for overnight.
  Cache in cache/reccobeats/. Nulls cached so failed tracks are skipped on retry.

Pass 2  — Last.fm API
  Fetches genre tags at track and artist level via pylast.
  Single-threaded at 0.25s/req (4 req/sec, under the 5 req/sec limit).
  Cache in cache/lastfm/.

All three caches are independent — if a run crashes or you re-run with new
files, only uncached tracks are fetched. You can skip any pass with a flag.

Output: output/enriched_tracks.json and output/enriched_tracks.csv

Usage:
  python enrich.py --files data/*.json
  python enrich.py --files data/*.json --skip-reccobeats --skip-lastfm   # Spotify only
  python enrich.py --files data/*.json --skip-lastfm                      # Spotify + ReccoBeats
  python enrich.py --files data/*.json --retry-nulls                      # retry ReccoBeats nulls
  python enrich.py --files data/*.json --limit 50                         # test run
  
"""


import argparse
import json
from src.logger import setup_logging,get_logger
import csv
from pathlib import Path

import src.spotify_client as sp_module
from src.spotify_client    import SpotifyEnricher
from src.reccobeats_client import ReccoBeatsEnricher
from src.lastfm_client     import LastFmEnricher

setup_logging()
logger =get_logger(__name__)

OUTPUT_DIR = Path("data/output")
OUTPUT_DIR.mkdir(exist_ok=True)

def save_json(data: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved → {path}")


def save_csv(data: list[dict], path: Path):
    if not data:
        return
    flat = []
    for row in data:
        flat_row = {}
        for k, v in row.items():
            flat_row[k] = "|".join(v) if isinstance(v, list) else v
        flat.append(flat_row)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat[0].keys())
        writer.writeheader()
        writer.writerows(flat)
    logger.info(f"Saved → {path}")


def load_unique_tracks(file_paths: list[Path]) -> list[dict]:
    """
    Parse raw Spotify JSON history files.
    Returns a deduplicated list of track dicts, skipping episodes/audiobooks.

    """
    seen_ids = set()
    tracks   = []

    for path in file_paths:
        logger.info(f"Reading {path}…")
        with open(path, encoding="utf-8") as f:
            plays = json.load(f)

        for play in plays:
            uri = play.get("spotify_track_uri")
            if not uri:
                continue  # podcast episode or audiobook — no track URI

            track_id = uri.split(":")[-1]
            if track_id in seen_ids:
                continue

            seen_ids.add(track_id)
            tracks.append({
                "track_id":    track_id,
                "track_name":  play.get("master_metadata_track_name"),
                "artist_name": play.get("master_metadata_album_artist_name"),
                "album_name":  play.get("master_metadata_album_album_name"),
                "uri":         uri,
            })


    logger.info(f"Found {len(tracks)} unique tracks across {len(file_paths)} file(s)")
    return tracks

def run_enrichment(
    raw_tracks: list[dict],
    skip_reccobeats: bool = False,
    skip_lastfm:     bool = False,
    retry_nulls:     bool = False,
) -> list[dict]:

    track_ids = [t["track_id"] for t in raw_tracks]

    # ---- Pass 1: Spotify ---- #
    logger.info("=" * 60)
    logger.info("PASS 1 — Spotify API (track + artist metadata)")
    logger.info("=" * 60)

    spotify    = SpotifyEnricher()
    track_meta = spotify.fetch_tracks(track_ids)

    artist_ids = list({
        meta["artist_id"]
        for meta in track_meta.values()
        if meta.get("artist_id")
    })
    logger.info(f"{len(artist_ids)} unique artists to fetch…")
    artist_meta = spotify.fetch_artists(artist_ids)
    spotify.save_all_caches()
    logger.info("Pass 1 complete.\n")

 # ---- Pass 1.5: ReccoBeats ----- #
    rb_results = {}
    if not skip_reccobeats:
        logger.info("=" * 60)
        logger.info("PASS 1.5 — ReccoBeats API (audio features)")
        logger.info(f"~2s per track — {len(track_ids)} tracks = ~{len(track_ids)*2//3600}h{(len(track_ids)*2%3600)//60}m estimated")
        logger.info("=" * 60)

        rb = ReccoBeatsEnricher(retry_nulls=retry_nulls)
        rb_results = rb.fetch_features(track_ids)
        rb.save_cache()
        logger.info("Pass 1.5 complete.\n")
    else:
        logger.info("ReccoBeats skipped (--skip-reccobeats)")

    # ---- Pass 2: Last.fm ---- #
    lfm_results = {}
    if not skip_lastfm:
        logger.info("=" * 60)
        logger.info("PASS 2 — Last.fm API (genre tags)")
        logger.info(f"~0.25s per track — {len(track_ids)} tracks = ~{len(track_ids)//4//3600}h{(len(track_ids)//4%3600)//60}m estimated")
        logger.info("Safe to leave overnight. Cache saves every 100 lookups.")
        logger.info("=" * 60)

        lfm = LastFmEnricher()
        lfm_results = lfm.enrich_tracks(raw_tracks)
        lfm.save_cache()
        logger.info("Pass 2 complete.\n")
    else:
        logger.info("Last.fm skipped (--skip-lastfm)")

    logger.info("Merging all enrichment data…")
    enriched = []

    for raw in raw_tracks:
        tid       = raw["track_id"]
        sp_track  = track_meta.get(tid, {})
        sp_artist = artist_meta.get(sp_track.get("artist_id", ""), {})
        rb        = rb_results.get(tid) or {}
        lfm       = lfm_results.get(tid) or {}

        enriched.append({
            # --- Identity ---
            "track_id":           tid,
            "track_uri":          raw["uri"],

            # --- Track metadata (Spotify) ---
            "track_name":         sp_track.get("track_name")      or raw["track_name"],
            "duration_ms":        sp_track.get("duration_ms"),
            "popularity":         sp_track.get("popularity"),
            "explicit":           sp_track.get("explicit"),
            "track_number":       sp_track.get("track_number"),
            "disc_number":        sp_track.get("disc_number"),

            # --- Artist (Spotify) ---
            "artist_id":          sp_track.get("artist_id"),
            "artist_name":        sp_track.get("artist_name")     or raw["artist_name"],
            "all_artist_names":   sp_track.get("all_artist_names", []),
            "artist_popularity":  sp_artist.get("popularity"),
            "artist_followers":   sp_artist.get("followers"),
            "spotify_genres":     sp_artist.get("genres", []),

            # --- Album (Spotify) ---
            "album_id":           sp_track.get("album_id"),
            "album_name":         sp_track.get("album_name")      or raw["album_name"],
            "album_release_date": sp_track.get("album_release_date"),
            "album_type":         sp_track.get("album_type"),
            "album_total_tracks": sp_track.get("album_total_tracks"),

            # --- Audio features (ReccoBeats) ---
            "danceability":       rb.get("danceability"),
            "energy":             rb.get("energy"),
            "valence":            rb.get("valence"),
            "tempo":              rb.get("tempo"),
            "loudness":           rb.get("loudness"),
            "acousticness":       rb.get("acousticness"),
            "instrumentalness":   rb.get("instrumentalness"),
            "speechiness":        rb.get("speechiness"),
            "liveness":           rb.get("liveness"),
            "key":                rb.get("key"),
            "mode":               rb.get("mode"),

            # --- Genre tags (Last.fm) ---
            "lastfm_track_tags":  lfm.get("lastfm_track_tags", []),
            "lastfm_artist_tags": lfm.get("lastfm_artist_tags", []),
        })

    return enriched
def main():
    parser = argparse.ArgumentParser(
        description="Enrich Spotify listening history with track, artist, audio feature, and genre data"
    )
    parser.add_argument(
        "--files", nargs="+", required=True,
        help="Raw Spotify JSON history file(s), e.g. data/2020.json data/2021.json"
    )
    parser.add_argument(
        "--skip-reccobeats", action="store_true",
        help="Skip ReccoBeats audio features pass"
    )
    parser.add_argument(
        "--skip-lastfm", action="store_true",
        help="Skip Last.fm genre tags pass"
    )
    parser.add_argument(
        "--retry-nulls", action="store_true",
        help="Retry ReccoBeats tracks previously returned as null (e.g. service was down)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process first N unique tracks — useful for a quick test run"
    )
    parser.add_argument(
        "--threads", type=int, default=None,
        help="Spotify API thread count (default 5). Try 8 for speed, 3 if seeing 429s"
    )
    args = parser.parse_args()

    if args.threads:
        sp_module.THREADS = args.threads
        logger.info(f"Spotify threads set to {args.threads}")

    file_paths = [Path(f) for f in args.files]
    missing    = [p for p in file_paths if not p.exists()]
    if missing:
        logger.error(f"File(s) not found: {missing}")
        return

    raw_tracks = load_unique_tracks(file_paths)

    if args.limit:
        logger.info(f"Limiting to first {args.limit} tracks (--limit)")
        raw_tracks = raw_tracks[:args.limit]

    enriched = run_enrichment(
        raw_tracks,
        skip_reccobeats = args.skip_reccobeats,
        skip_lastfm     = args.skip_lastfm,
        retry_nulls     = args.retry_nulls,
    )

    save_json(enriched, OUTPUT_DIR / "enriched_tracks.json")
    save_csv(enriched,  OUTPUT_DIR / "enriched_tracks.csv")

    logger.info(f"\nDone. {len(enriched)} tracks enriched → {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()