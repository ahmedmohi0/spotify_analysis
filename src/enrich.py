import argparse
import json
from src.logger import setup_logging,get_logger
import csv
from pathlib import Path

import spotify_client as sp_module
from spotify_client    import SpotifyEnricher
from reccobeats_client import ReccoBeatsEnricher
from lastfm_client     import LastFmEnricher

setup_logging()
logger =get_logger(__name__)


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
