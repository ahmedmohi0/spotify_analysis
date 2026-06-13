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

CACHE_DIR = Path("cache/spotify")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TRACK_CACHE_FILE    = CACHE_DIR / "tracks.json"
FEATURES_CACHE_FILE = CACHE_DIR / "audio_features.json"
ARTIST_CACHE_FILE   = CACHE_DIR / "artists.json"

BATCH_SIZE   = 50   
SLEEP_BATCH  = 0.5  
MAX_RETRIES  = 5
RETRY_BACKOFF = 2

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
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args,**kwargs)
        #raise a runtime error if error not found in listed errors
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == "429":
                wait = RETRY_BACKOFF ** attempt
                logger.warning(f"Too many requests retrying the {attempt+1} attempt after {wait} seconds")
                time.sleep(wait)
            elif e.http_status in (500,502,503):
                wait = RETRY_BACKOFF ** attempt
                logger.warning(f"Server error retrying the {attempt+1} attempt after {wait} seconds")
            else:
                raise
            raise RuntimeError(f"Failed after {MAX_RETRIES} retries")

#The original plan was using get tracks which I missed that its no longer supported
# also get audio_features no longer supported so the code and the structure are gonna change        
"""
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

        self.track_cache = load_cache(TRACK_CACHE_FILE)
        self.features_cache = load_cache (FEATURES_CACHE_FILE)
        self.artists_cache = load_cache(ARTIST_CACHE_FILE)

        logger.info(
            f"Cache loaded: {len(self.track_cache)} tracks | "
            f"{len(self.features_cache)} audio features | "
            f"{len(self.artist_cache)} artists"
        )
    
    def fetch_tracks(self:self,track_ids:list[str]) -> dict[str,dict]:
        
        Fetch track metadata for a list of Spotify track IDs.
        Returns dict of {track_id: track_data}.
        
        missing = [tid for tid in track_ids if tid not in self.track_cache]
        logger.info(f"Tracks: {len(track_ids)} requested | {len(missing)} not cached")
        for i in range(0,len(missing),BATCH_SIZE):
            batch = missing[i,i+BATCH_SIZE]
            logger.info (f"Fetching tracks batch {i // BATCH_SIZE + 1} ({len(batch)} tracks)…")
            result = retry(self.sp.tracks,batch)
            for track in result["tracks"]:
                if track:
                    self.track_cache[track["id"]] = extract_track(track)
            
            save_cache(TRACK_CACHE_FILE,self.track_cache)
            time.sleep(SLEEP_BATCH)
            #dictionary comprehension
        return {tid: self.track_cache[tid] for tid in track_ids if tid in self.track_cache}
    
    def fetch_audio_features(self,track_ids:list[str]) -> dict[str,dict]:
        
        Fetch audio features for a list of Spotify track IDs.
        Returns dict of {track_id: features_data}.
        
        missing = [tid for tid in track_ids if tid not in self.features_cache]
        logger.info(f"tracks: {len(track_ids)}requested , {missing} missing from cache")
        for i in range(0,len(missing),BATCH_SIZE):
            batch = missing[i : i + BATCH_SIZE]
            logger.info(f"Fetching audio features batch {i // BATCH_SIZE + 1} ({len(batch)} tracks)…")
            result = retry(self.sp.audio_features,batch)
            for f in result:
                if f:
                    self.features_cache[f["id"]] = extract_audio_features(f)
            save_cache(FEATURES_CACHE_FILE,self.features_cache)
            time.sleep(SLEEP_BATCH)
        
        return{tid:self.features_cache[tid] for tid in track_ids if tid in self.features_cache}
"""




def extract_track(t: dict) -> dict:
    artists = t.get("artists", [])
    album   = t.get("album", {})
    #Here we use .get when the information may return none and [] when the key must exist like track id
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

def extract_audio_features(t:dict) -> dict:
    pass

