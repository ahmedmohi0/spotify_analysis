import json
from pathlib import Path

import pandas as pd

from src.config import RAW_DATA_DIR,RAW_JSON_DIR
from src.DB import get_connection
from src.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

STAGING_COLUMNS = [
    "track_id", "track_uri", "track_name", "duration_ms", "popularity", "explicit",
    "track_number", "disc_number", "artist_id", "artist_name", "all_artist_names",
    "album_id", "album_name", "album_release_date", "album_type", "album_total_tracks",
    "danceability", "energy", "valence", "tempo", "loudness", "acousticness",
    "instrumentalness", "speechiness", "liveness", "key", "mode",
    "lastfm_track_tags", "lastfm_artist_tags",
    "played_at", "ms_played", "shuffled", "skipped", "reason_start", "reason_end", "offline",
]

def load_json_files(json_paths: list[Path]) -> pd.DataFrame:
    """
    Load multiple JSON files and return a list of dicts.
    """
    records = []

    for path in json_paths:
        logger.info(f"Loading {path}…")
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
            logger.info(f"  Loaded {len(items)} items from {path}")
        for item in items:
            item_uri = item.get("spotify_track_uri")
            if not item_uri:
                continue
            track_id = item_uri.split(":")[-1]
        
            records.append({
            "track_id":    track_id,
            "track_name":  item.get("master_metadata_track_name"),
            "ms_played":    item.get("ms_played"),
            "reason_start":  item.get("reason_start"),
            "reason_end":    item.get("reason_end"),
            "shuffled":      item.get("shuffle"),
            "offline":       item.get("offline"),
            "timestamp":     item.get("ts"),
            "skipped":        item.get("skipped")
            })
    plays = pd.DataFrame.from_records(records)
    logger.info(f"Total items loaded: {len(plays)}")
    return plays    


def load_enriched_tracks(csv_path: Path) -> pd.DataFrame:
    """
    Load enriched_tracks.csv (output of enrich.py).
    """
    logger.info(f"Loading enriched tracks from {csv_path}…")
    enriched_df = pd.read_csv(csv_path)
    logger.info(f"  Loaded {len(enriched_df)} items from {csv_path}")
    return enriched_df

def parse_list_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Convert pipe-delimited string columns (tags, all_artist_names)
    back into real Python lists. Modifies and returns df.
    """
    logger.info(f"Parsing list columns: {columns}")
    for col in columns:
        df[col] = df[col].str.split("|").apply(lambda x: [i.strip() for i in x] if isinstance(x, list) else [])
    logger.info("List columns parsed.")
    return df


def merge_plays_with_enrichment(
    plays_df: pd.DataFrame, enriched_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Left-join plays_df to enriched_df on track_id. Logs any track_ids
    in plays_df with no enrichment match.
    """
    logger.info("Merging plays with enrichment data…")
    plays_df['track_id'] = plays_df['track_id'].astype(str)
    enriched_df['track_id'] = enriched_df['track_id'].astype(str)
    merged_df = plays_df.merge(enriched_df, on="track_id", how="left", suffixes=("", "_enriched"),indicator=True,validate="m:1")
    missing_mask = merged_df["_merge"] == "left_only"
    n_missing = missing_mask.sum()
    logger.info(f"  Missing enrichment for {n_missing} plays")
    if n_missing:
        missing_ids = merged_df.loc[missing_mask, "track_id"].unique()
        logger.info(f"  Affected track_ids ({len(missing_ids)} unique): {list(missing_ids)[:20]}")

    merged_df.drop(columns=["_merge"], inplace=True)
    logger.info("Merge complete.")
    return merged_df

def cast_for_staging(df: pd.DataFrame) -> pd.DataFrame:
    """
    Selects, renames, and casts the merged dataframe to exactly match
    staging_listening_history's columns (staging_id excluded — it's a
    SERIAL primary key, Postgres assigns it).
    """
    logger.info("Casting merged dataframe for staging…")
    df = df.copy()

    df = df.rename(columns={"timestamp": "played_at"})
    if "track_name_enriched" in df.columns:
        df["track_name"] = df["track_name_enriched"]
        df.drop(columns=["track_name_enriched"], inplace=True)
        df["played_at"] = pd.to_datetime(df["played_at"])

    missing = [c for c in STAGING_COLUMNS if c not in df.columns]
    if missing:
        logger.warning(f"Columns missing before staging (filled as NULL): {missing}")

    df = df.reindex(columns=STAGING_COLUMNS)

    logger.info(f"Cast {len(df)} rows to staging shape.")
    return df


if __name__ == "__main__":
    test_files = [Path("data\\raw\\Streaming_History_Audio_2020.json")]  
    df = load_json_files(test_files)
    print(df.shape)
    print(df.head())