
import json
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)


TEST_IDS = [
    "6bfTuM7FMLwiYC4fv2upLo",  # Fairouz — El Bent El Shalabeya
    "3n3Ppam7vgaVa1iaRUIOKE",  # Paranoid Android — Radiohead
    "0VjIjW4GlUZAMYd2vXMi3b",  # Blinding Lights — The Weeknd
]

BASE_URL = "https://api.reccobeats.com/v1/audio-features"

session = requests.Session()
session.headers.update({"Accept": "application/json"})

print("=" * 60)
print(f"Sending {len(TEST_IDS)} IDs to {BASE_URL}")
print(f"IDs: {TEST_IDS}")
print("=" * 60)

resp = session.get(
    BASE_URL,
    params={"ids": ",".join(TEST_IDS)},
    timeout=30,
)

print(f"\nStatus code: {resp.status_code}")
print(f"Response headers: {dict(resp.headers)}")
print("\n--- RAW RESPONSE BODY ---")

try:
    parsed = resp.json()
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    
except requests.exceptions.JSONDecodeError:
    print("Response is not JSON:")
    print(resp.text)