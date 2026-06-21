import os
import time
import json
import logging
from pathlib import Path
import spotipy
from dotenv import load_dotenv
from concurrent.futures import as_completed,ThreadPoolExecutor
import threading
from src.logger import setup_logging, get_logger

setup_logging()

logger = get_logger(__name__)
load_dotenv()

CACHE_DIR = Path("cache/spotify")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TRACK_CACHE_FILE    = CACHE_DIR / "tracks.json"
#FEATURES_CACHE_FILE = CACHE_DIR / "audio_features.json"
ARTIST_CACHE_FILE   = CACHE_DIR / "artists.json"

THREADS = 5
SLEEP_BETWEEN  = 0.3
MAX_RETRIES  = 5
RETRY_BACKOFF = 2
CACHE_SAVE_EVERY_N = 100

def load_cache(path:Path ) -> dict:
    if path.exists():
        with open(path,encoding= "utf-8") as f:
            return json.load(f)
    return{}

def save_cache(path:Path,data:dict):
    tmp = path.with_suffix(".tmp")
    with open(tmp,"w",encoding= 'utf-8') as f:
        json.dump(data,f,ensure_ascii=False)
    tmp.replace(path)

def retry(fn, *args, **kwargs):
    
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)

        except spotipy.exceptions.SpotifyException as e:

            if e.http_status == 429:
                wait = RETRY_BACKOFF ** attempt
                logger.warning(
                    f"Rate limited. Retrying in {wait}s"
                )
                time.sleep(wait)

            elif e.http_status in (500, 502, 503):
                wait = RETRY_BACKOFF ** attempt
                logger.warning(
                    f"Server error. Retrying in {wait}s"
                )
                time.sleep(wait)

            else:
                raise

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} retries"
    )
class SpotifyEnricher:
    def __init__(self):
        client_id     = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET.\n"
                "Copy .env.example to .env and fill in your credentials."
            )
        #each thread becomes a container other threads can't see
        self.local = threading.local()
        # Store credentials — each thread builds its own client
        self._credentials = (client_id, client_secret)

        # Caches shared across threads, protected by locks
        self.track_cache  = load_cache(TRACK_CACHE_FILE)
        self.artist_cache = load_cache(ARTIST_CACHE_FILE)
        self._track_lock  = threading.Lock()
        self._artist_lock = threading.Lock()
        logger.info(
            f"Spotify cache: {len(self.track_cache)} tracks | "
            f"{len(self.artist_cache)} artists"
        )

    def make_client(self) -> spotipy.Spotify:
        """creating one client for each thread """
        if not hasattr(self.local,"client"):
            client_id,client_secret = self._credentials
            self.local.client = spotipy.Spotify(auth_manager = spotipy.oauth2.SpotifyClientCredentials(client_id = client_id,client_secret = client_secret))
        return self.local.client

    def fetch_tracks(self,track_ids:list [str])->dict[str,dict]:
        with self._track_lock:
            missing = [tid for tid in track_ids if tid not in self.track_cache]

        logger.info(
            f"Tracks: {len(track_ids)} total | "
            f"{len(track_ids) - len(missing)} cached | "
            f"{len(missing)} to fetch | "
            f"{THREADS} threads"
        )
        if not missing:
            return {tid: self.track_cache[tid] for tid in track_ids if tid in self.track_cache}
        fetched_count = 0
        def fetch_one(track_id:str) ->tuple[str, dict | None]:
            sp = self.make_client()
            try:
                result = retry(sp.track,track_id)
                time.sleep(SLEEP_BETWEEN)
                return track_id,extract_track(result)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404:
                    logger.debug(f"Track not found (404): {track_id}")
                    return track_id, None
                raise
        
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = {executor.submit(fetch_one,tid):tid for tid in missing}
            for future in as_completed(futures):
                track_id,data = future.result()
                fetched_count += 1

                if data:
                    with self._track_lock:
                        self.track_cache[track_id] = data
                        if fetched_count % CACHE_SAVE_EVERY_N == 0:
                            save_cache (TRACK_CACHE_FILE, self.track_cache)
                            logger.info(f"  Tracks progress: {fetched_count}/{len(missing)}")
        with self._track_lock:
            save_cache(TRACK_CACHE_FILE,self.track_cache)
        logger.info(f"Tracks done: {fetched_count} fetched")
        return {tid: self.track_cache[tid] for tid in track_ids if tid in self.track_cache}   

    def fetch_artists(self,artist_ids:list[str]) -> dict[str:dict]:
        """
        Fetch artist metadata for a list of artist IDs.
        Uses THREADS workers, each calling GET /artist/{id}.
        Returns dict of {artist_id: artist_data}.
        """
         
        with self._artist_lock:
            missing = [aid for aid in artist_ids if aid not in self.artist_cache] 
        logger.info(
            f"Artists: {len(artist_ids)} total | "
            f"{len(artist_ids) - len(missing)} cached | "
            f"{len(missing)} to fetch | "
            f"{THREADS} threads"
        )
        if not missing:
            return{aid:self.artist_cache[aid] for aid in artist_ids if aid in self.artist_cache}
        
        fetched_count = 0
        def fetch_one(artist_id:str) -> tuple[str, dict | None]:
            sp = self.make_client()
            try:
                result = retry(sp.artist,artist_id)
                time.sleep(SLEEP_BETWEEN)
                return artist_id , extract_artist(result)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404:
                    logger.debug(f"artist not found (404): {artist_id}")
                    return artist_id, None
            
                raise
        with ThreadPoolExecutor(max_workers= THREADS) as executor:
            futures = {executor.submit(fetch_one,aid):aid for aid in missing}
            for future in as_completed(futures):
                artist_id,data = future.result()
                fetched_count += 1
                if data:
                    with self._artist_lock:
                        self.artist_cache[artist_id] = data
                        if fetched_count % CACHE_SAVE_EVERY_N == 0:
                                save_cache (ARTIST_CACHE_FILE, self.artist_cache)
                                logger.info(f"artists progress: {fetched_count}/{len(missing)}")
        with self._artist_lock:
            save_cache(ARTIST_CACHE_FILE,self.artist_cache)
        logger.info(f"artists done: {fetched_count} fetched")
        return {aid: self.artist_cache[aid] for aid in artist_ids if aid in self.artist_cache} 

    def save_all_caches(self):
        with self._track_lock:
            save_cache(TRACK_CACHE_FILE, self.track_cache)
        with self._artist_lock:
            save_cache(ARTIST_CACHE_FILE, self.artist_cache)



def extract_track(t: dict) -> dict:
    artists = t.get("artists", [])
    album   = t.get("album", {})
    # Use [] for required fields and .get() for optional fields
    return {
        "track_id":           t["id"],
        "track_name":         t["name"],
        "duration_ms":        t.get("duration_ms"),
        "popularity":         t.get("popularity"),
        "explicit":           t.get("explicit"),
        "track_number":       t.get("track_number"),
        "disc_number":        t.get("disc_number"),
        # Primary artist
        "artist_id":          artists[0]["id"] if artists else None,
        "artist_name":        artists[0]["name"] if artists else None,
        # All artists (for collaborations)
        "all_artist_ids":     [a["id"] for a in artists],
        "all_artist_names":   [a["name"] for a in artists],
        # Album
        "album_id":           album.get("id"),
        "album_name":         album.get("name"),
        "album_release_date": album.get("release_date"),
        "album_type":         album.get("album_type"),     
        "album_total_tracks": album.get("total_tracks"),
    }

def extract_artist(a: dict) -> dict:
    return {
        "artist_id":   a["id"],
        "artist_name": a.get("name"),
        "genres":      a.get("genres", []),
        "popularity":  a.get("popularity"),
        "followers":   a.get("followers", {}).get("total"),
    }
