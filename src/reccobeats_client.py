import json
import time
import logging
from pathlib import Path
from src.logger import setup_logging,get_logger
import requests

setup_logging()
logger = get_logger(__name__)

CACHE_DIR      = Path("cache/reccobeats")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE     = CACHE_DIR / "audio_features.json"

BASE_URL       = "https://api.reccobeats.com/v1/track"
SLEEP_BETWEEN  = 2.0   
CACHE_SAVE_EVERY = 50  
MAX_RETRIES    = 4
RETRY_BACKOFF  = 3     

def _load_cache(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)

class ReccoBeatsEnricher:
    def __init__(self, retry_nulls: bool = False):
        """
        retry_nulls: if True, re-attempt tracks previously cached as None.
        """
        self.cache       = _load_cache(CACHE_FILE)
        self.retry_nulls = retry_nulls
        self.session     = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        cached_found = sum(1 for v in self.cache.values() if v is not None)
        cached_null  = sum(1 for v in self.cache.values() if v is None)
        logger.info(
            f"ReccoBeats cache: {cached_found} found | "
            f"{cached_null} nulls | "
            f"retry_nulls={retry_nulls}"
        )

    def save_cache(self):
        _save_cache(CACHE_FILE, self.cache)
        
def _extract_features(data: dict) -> dict:
    """
    Pull the audio feature fields from the ReccoBeats response.
    """
    return {
        "danceability":     data.get("danceability"),
        "energy":           data.get("energy"),
        "valence":          data.get("valence"),
        "tempo":            data.get("tempo"),
        "loudness":         data.get("loudness"),
        "acousticness":     data.get("acousticness"),
        "instrumentalness": data.get("instrumentalness"),
        "speechiness":      data.get("speechiness"),
        "liveness":         data.get("liveness"),
        "key":              data.get("key"),
        "mode":             data.get("mode"),
        "time_signature":   data.get("time_signature"),
    }