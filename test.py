# import logging
# from src.spotify_client import SpotifyEnricher

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s  %(levelname)-8s  %(message)s",
#     datefmt="%H:%M:%S",
# )

# # A few real Spotify track IDs to test with
# TEST_TRACK_IDS = [
#     "6bfTuM7FMLwiYC4fv2upLo",  
#     "3n3Ppam7vgaVa1iaRUIOKE", 
# ]

# enricher = SpotifyEnricher()

# # Test track fetching
# print("\n--- TRACKS ---")
# tracks = enricher.fetch_tracks(TEST_TRACK_IDS)
# for tid, data in tracks.items():
#     print(f"{tid}: {data}")

# # Test artist fetching — pull artist IDs from what we just got
# artist_ids = [t["artist_id"] for t in tracks.values() if t and t.get("artist_id")]

# print("\n--- ARTISTS ---")
# artists = enricher.fetch_artists(artist_ids)
# for aid, data in artists.items():
#     print(f"{aid}: {data}")

import logging
from src.lastfm_client import LastFmEnricher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# Mix of tracks — Arabic, Western, niche — to test coverage
TEST_TRACKS = [
    {
        "track_id":    "abc001",
        "track_name":  "El Bent El Shalabeya",
        "artist_name": "Fairuz",
    },
    {
        "track_id":    "abc002",
        "track_name":  "Paranoid Android",
        "artist_name": "Radiohead",
    },
    {
        "track_id":    "abc003",
        "track_name":  "Blinding Lights",
        "artist_name": "The Weeknd",
    },
]

enricher = LastFmEnricher()
results  = enricher.enrich_tracks(TEST_TRACKS)

print("\n--- RESULTS ---")
for track in TEST_TRACKS:
    tid  = track["track_id"]
    name = track["track_name"]
    data = results.get(tid, {})
    print(f"\n{name}")
    print(f"  track tags:  {data.get('lastfm_track_tags')}")
    print(f"  artist tags: {data.get('lastfm_artist_tags')}")