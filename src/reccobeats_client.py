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

BASE_URL       = "https://api.reccobeats.com/v1/audio-features"
SLEEP_BETWEEN  = .5 
CACHE_SAVE_EVERY = 10  
MAX_RETRIES    = 4
RETRY_BACKOFF  = 3     
BATCH_SIZE = 40
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

    def fetch_features(self, track_ids: list[str]) -> dict[str, dict | None]:
        """
        Fetch audio features for a list of Spotify track IDs.
        Sends batches of BATCH_SIZE to GET /v1/audio-features?ids=...
        Returns dict of {track_id: features_dict | None}.
        """
        if self.retry_nulls:
            missing = [tid for tid in track_ids if tid not in self.cache]
        else:
            missing = [
                tid for tid in track_ids
                if tid not in self.cache and self.cache.get(tid) is not None
            ]
            already_null = [tid for tid in track_ids if self.cache.get(tid) is None]
            if already_null:
                logger.info(
                    f"  Skipping {len(already_null)} previously null tracks "
                    f"(use --retry-nulls to retry)"
                )

        logger.info(
            f"ReccoBeats: {len(track_ids)} total | "
            f"{len(track_ids) - len(missing)} cached | "
            f"{len(missing)} to fetch | "
            f"{(len(missing) + BATCH_SIZE - 1) // BATCH_SIZE} batches"
        )

        if not missing:
            return {tid: self.cache.get(tid) for tid in track_ids}

        batches       = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        batch_count   = 0
        fetched_count = 0

        for batch in batches:
            results = self._fetch_batch(batch)

            # Store results — None for any ID not returned by the API
            for tid in batch:
                self.cache[tid] = results.get(tid)  # None if missing from response
            fetched_count += len(batch)
            batch_count   += 1

            if batch_count % CACHE_SAVE_EVERY == 0:
                _save_cache(CACHE_FILE, self.cache)
                found = sum(1 for v in self.cache.values() if v is not None)
                logger.info(
                    f"  ReccoBeats: {fetched_count}/{len(missing)} tracks processed | "
                    f"{found} total with features"
                )

            time.sleep(SLEEP_BETWEEN)


        _save_cache(CACHE_FILE, self.cache)
        found = sum(1 for tid in missing if self.cache.get(tid) is not None)
        logger.info(
            f"ReccoBeats done: {fetched_count} tracks processed | "
            f"{found} with features | "
            f"{fetched_count - found} no data"
        )

        return {tid: self.cache.get(tid) for tid in track_ids}

    def _fetch_batch(self, track_ids: list[str]) -> dict[str, dict]:
        """
        Fetch a batch of up to BATCH_SIZE tracks from ReccoBeats.
        Passes Spotify IDs as comma-separated query param.
        Returns dict of {track_id: features_dict} for tracks that had data.
        Missing tracks are simply absent from the returned dict.
        """
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(
                    BASE_URL,
                    params={"ids": ",".join(track_ids)},
                    timeout=30,   # batch requests need more time than single
                )

                if resp.status_code == 200:
                    return _extract_batch(resp.json())

                elif resp.status_code == 429:
                    wait = RETRY_BACKOFF ** (attempt + 1)
                    logger.warning(
                        f"ReccoBeats rate limited (429). "
                        f"Waiting {wait}s [attempt {attempt+1}/{MAX_RETRIES}] — "
                        f"consider increasing SLEEP_BETWEEN"
                    )
                    time.sleep(wait)

                elif resp.status_code in (500, 502, 503):
                    wait = RETRY_BACKOFF ** (attempt + 1)
                    logger.warning(
                        f"ReccoBeats server error {resp.status_code}. "
                        f"Waiting {wait}s [attempt {attempt+1}/{MAX_RETRIES}]"
                    )
                    time.sleep(wait)

                else:
                    logger.warning(
                        f"ReccoBeats unexpected {resp.status_code} "
                        f"for batch of {len(track_ids)}"
                    )
                    return {}

            except requests.exceptions.Timeout:
                logger.warning(f"ReccoBeats timeout [attempt {attempt+1}]")
                time.sleep(RETRY_BACKOFF ** (attempt + 1))

            except requests.exceptions.ConnectionError:
                logger.warning(f"ReccoBeats connection error [attempt {attempt+1}]")
                time.sleep(RETRY_BACKOFF ** (attempt + 1))

        logger.warning(f"ReccoBeats gave up after {MAX_RETRIES} attempts on batch")
        return {}
    
    def save_cache(self):
        _save_cache(CACHE_FILE, self.cache)

def _extract_batch(response: dict | list) -> dict[str, dict]:
    """
    Maps results back to Spotify IDs using the href field.
    The 'id' field in each item is a ReccoBeats UUID, not the Spotify ID.
    The 'href' field always ends with the Spotify track ID:
      e.g. "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUIOKE"
    ReccoBeats skips tracks with no data entirely so we can't map by
    position — href is the only reliable mapping key.
    """
    results = {}

    items = response if isinstance(response, list) else response.get("content", [])

    for item in items:
        if not item:
            continue

        href = item.get("href")
        if not href:
            continue

        spotify_id = href.split("/")[-1]
        if not spotify_id:
            continue

        results[spotify_id] = _extract_features(item)

    return results


def _extract_features(data: dict) -> dict:
    """
    Pull audio feature fields from a ReccoBeats feature object.
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
        "mode":             data.get("mode")
    }