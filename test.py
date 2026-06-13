import os
import time
import json
import logging
from pathlib import Path
import spotipy
from dotenv import load_dotenv
import pprint

load_dotenv()
client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(client_id,client_secret) 
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)


track_id = "11dFghVXANMlKmJXsNCbNl"
tracks_ids = "7ouMYWpwJ422jRcDASZB7P,4VqPOruhp5EdPBeR92t6lQ,2takcwOaAZWiXQijPHIx7B".split(",")
track = sp.audio_features (tracks_ids)
pprint.pprint(track)

"""
def extract_track(t: dict) -> dict:
    artists = t.get("artists", [])
    album   = t.get("album", {})
    return {
        "track_id":           t["id"],
        "track_name":         t.get("name"),
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

f = extract_track(track)
print(f)
"""



