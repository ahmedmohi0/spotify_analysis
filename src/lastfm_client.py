import os
import json
import time
from pathlib import Path
from src.logger import setup_logging,get_logger
import pylast
from dotenv import load_dotenv

setup_logging()
logger = get_logger(__name__)

load_dotenv()

CACHE_DIR     = Path("cache/lastfm")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE    = CACHE_DIR / "lastfm_tags.json"


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

MIN_WEIGHT       = 10       # drop tags with weight below this (0-100 scale)
MAX_TAGS_TRACK   = 5        # keep top N tags per track 
MAX_TAGS_ARTIST  = 10       # keep top N tags per artist
CACHE_SAVE_EVERY = 100      # save to disk every N new lookups
SLEEP_BETWEEN    = 0.25     # 4 req\sec (lastfm rate limit is 5 req\sec)
MAX_RETRIES      = 3        # max number of retries before returning null
RETRY_BACKOFF    = 2  

class LastFmEnricher:
    def __init__(self):
        api_key = os.getenv("api_key")
        shared_secret = os.getenv("shared_secret")
        if not api_key or not shared_secret:
            raise EnvironmentError(
                "Missing LASTFM_API_KEY or LASTFM_API_SECRET.\n"
                "Get a free key at https://www.last.fm/api/account/create\n"
                "then add both to your .env file."
            )
        self.network = pylast.LastFMNetwork(api_key=api_key , api_secret= shared_secret)

        self.cache = _load_cache(CACHE_FILE)

    

    def empty() -> dict:
        return {
            "lastfm_track_tags":  [],
            "lastfm_artist_tags": [],
        }
    
    def save_cache(self):
        _save_cache(CACHE_FILE,self.cache)

    def _get_track_tags(self, artist: str, track: str) -> list[str]:
        """
        Fetch top tags for a specific track.
        """
        for attempt in range (MAX_RETRIES):
            try:
                lfm_track = self.network.get_track(artist,track)
                top_tags = lfm_track.get_top_tags()
                return parse_track_tags(top_tags)   
            except pylast.WSError as e:
                
                if "not found" in str(e).lower() or "invalid" in str(e).lower():
                    logger.debug(f"Last.fm track not found: '{track}' by '{artist}'")
                    return []
                logger.warning(f"Last.fm WSError (track tags) [{attempt+1}]: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

            except pylast.NetworkError as e:
                logger.warning(f"Last.fm NetworkError (track tags) [{attempt+1}]: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

        return []
    
    def _get_artist_tags(self, artist: str) -> list[str]:
        """
        Fetch top tags for an artist.
        Artist tags are broader and more reliable than track tags
        for genre classification — useful as fallback when track tags are sparse.
        """
        for attempt in range(MAX_RETRIES):
            try:
                lfm_artist = self.network.get_artist(artist)
                top_tags   = lfm_artist.get_top_tags()
                return parse_artist_tags(top_tags)

            except pylast.WSError as e:
                if "not found" in str(e).lower() or "invalid" in str(e).lower():
                    logger.debug(f"Last.fm artist not found: '{artist}'")
                    return []
                logger.warning(f"Last.fm WSError (artist tags) [{attempt+1}]: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

            except pylast.NetworkError as e:
                logger.warning(f"Last.fm NetworkError (artist tags) [{attempt+1}]: {e}")
                time.sleep(RETRY_BACKOFF ** attempt)

        return []   
    def _lookup(self, artist: str, track: str) -> dict:
        """
        Fetch track-level and artist-level tags from Last.fm.
        Returns dict with lastfm_track_tags and lastfm_artist_tags.
        """
        track_tags  = self._get_track_tags(artist, track)
        artist_tags = self._get_artist_tags(artist)

        return {
            "lastfm_track_tags":  track_tags,
            "lastfm_artist_tags": artist_tags,
        }
    def enrich_tracks(self, tracks: list[dict]) -> dict[str, dict]:
        """
        Fetch Last.fm genre tags for a list of track dicts.
        Each dict needs: track_id, track_name, artist_name.
        Returns dict of {track_id: lastfm_data}.
        """
        new_hits = 0
        skipped  = 0
        results  = {}

        for track in tracks:
            track_id    = track["track_id"]
            artist_name = track.get("artist_name", "")
            track_name  = track.get("track_name", "")

           
            cache_key = f"{artist_name.lower()}||{track_name.lower()}"

            if cache_key in self.cache:
                results[track_id] = self.cache[cache_key]
                skipped += 1
                continue

            data = self._lookup(artist_name, track_name)

            self.cache[cache_key] = data
            results[track_id]     = data
            new_hits += 1

            if new_hits % CACHE_SAVE_EVERY == 0:
                _save_cache(CACHE_FILE, self.cache)
                logger.info(
                    f"  Last.fm: {new_hits} fetched | "
                    f"{skipped} from cache | "
                    f"{len(tracks) - new_hits - skipped} remaining"
                )

            time.sleep(SLEEP_BETWEEN)

        _save_cache(CACHE_FILE, self.cache)
        logger.info(
            f"Last.fm complete: {new_hits} fetched | {skipped} from cache"
        )
        return results
    

def parse_track_tags(top_tags: list) -> list[str]:
        """
        Filter and sort Last.fm TopItem tag objects.
        Each item has: item.name (tag string) and weight (int 0-100).
        Drops tags below MIN_WEIGHT, returns top MAX_TAGS names.
        """
        filtered = [
            t for t in top_tags
            if int(t.weight) >= MIN_WEIGHT
        ]
        filtered.sort(key=lambda t: int(t.weight), reverse=True)
        return [t.item.name.lower() for t in filtered[:MAX_TAGS_TRACK]]

def parse_artist_tags(top_tags: list) -> list[str]:
        """
        Filter and sort Last.fm TopItem tag objects.
        Each item has: item.name (tag string) and weight (int 0-100).
        Drops tags below MIN_WEIGHT, returns top MAX_TAGS names.
        """
        filtered = [
            t for t in top_tags
            if int(t.weight) >= MIN_WEIGHT
        ]
        filtered.sort(key=lambda t: int(t.weight), reverse=True)
        return [t.item.name.lower() for t in filtered[:MAX_TAGS_ARTIST]]
