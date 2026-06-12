import os
import time
import json
import logging
from pathlib import Path
import spotipy
from dotenv import load_dotenv

load_dotenv()
logger = logging.getlogger(__name__)

cache_dir = Path("cache/spotify")
cache_dir.mkdir(parents=True,exist_ok=True)

tracks_cache_files = cache_dir / "tracks.json"
features_cache_files = cache_dir / "features.json"
artists_cache_files = cache_dir / "artists.json"

batch_size = 5
sleep = .5
max_retries = 5
retry_backoff = 2

def load_cache(path:Path ) -> dict:
    if Path.exists():
        with open(path) as f:
            return json.load(f)
    return{}

def save_cache(path:Path,data:dict):
    with open(path,"w") as f:
        json.dump(data,f)

def retry(fn,*args,**kwargs):
    """call a function with exponential back off on rate limit or errors."""
    for attempt in range(max_retries):
        try:
            return fn(*args,**kwargs)
        #raise a runtime error if error not found in listed errors
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == "429":
                wait = retry_backoff ** attempt
                logger.warning(f"Too many requests retrying the {attempt+1} attempt after {wait} seconds")
                time.sleep(wait)
            elif e.http_status in (500,502,503):
                wait = retry_backoff ** attempt
                logger.warning(f"Server error retrying the {attempt+1} attempt after {wait} seconds")
            else:
                raise
            raise RuntimeError(f"Failed after {max_retries} retries")

class Spotify_Enricher:
    def __init__(self):
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET. "
                "Copy .env.example to .env and fill in your credentials."
            )
        
        client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(client_id,client_secret) 
        self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        self.track_cache = load_cache(tracks_cache_files)
        self.features_cache = load_cache (features_cache_files)
        self.artists_cache = load_cache(artists_cache_files)
        
        logger.info(
            f"Cache loaded: {len(self.track_cache)} tracks | "
            f"{len(self.features_cache)} audio features | "
            f"{len(self.artist_cache)} artists"
        )