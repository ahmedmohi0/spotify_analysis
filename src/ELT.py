import json
import ast
from pathlib import Path

import pandas as pd

from src.config import RAW_DATA_DIR,RAW_JSON_DIR
from src.DB import get_connection
from src.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

def load_json_files(json_paths: list[Path]) -> pd.DataFrame:
    """
    Load multiple JSON files and return a list of dicts.
    """
    data = pd.DataFrame()

    for path in json_paths:
        logger.info(f"Loading {path}…")
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            item_uri = item.get("spotify_track_uri")
            if not item_uri:
                continue
            track_id = item_uri.split(":")[-1]
        
            track_data = {
            "track_id":    track_id,
            "track_name":  item.get("master_metadata_track_name"),
            "ms_played":    item.get("ms_played"),
            "reason_start":  item.get("reason_start"),
            "reason_end":    item.get("reason_end"),
            "shuffled":      item.get("shuffle"),
            "offline":       item.get("offline"),
            "timestamp":     item.get("ts")}
            data = pd.concat([data, pd.DataFrame([track_data])], ignore_index=True)
    return data    

if __name__ == "__main__":
    test_files = [Path("data\\raw\\Streaming_History_Audio_2020.json")]  
    df = load_json_files(test_files)
    print(df.shape)
    print(df.head())