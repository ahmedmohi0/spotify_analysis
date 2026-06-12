import os
import time
import json
import logging
from pathlib import Path
import spotipy
from dotenv import load_dotenv

load_dotenv()
client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

client_credentials_manager = spotipy.oauth2.SpotifyClientCredentials(client_id,client_secret) 
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)



urn = 'spotify:album:5yTx83u3qerZF7GRJu7eFk'
# retrieves album information in json format
album = sp.album(urn)
# formatted print of the result
print(album)
