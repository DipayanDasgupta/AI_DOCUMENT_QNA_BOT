# backend/app/core/state.py
from typing import Dict, Any

# --- Simple In-Memory Stores ---
# WARNING: Lost on server restart! Replace with persistent storage/DB for production.

# Structure: { session_id: {"status": "processing/ready/error", "message": "Optional details"} }
session_status_store: Dict[str, Dict[str, str]] = {}

# You could potentially move other shared stores here too if needed later
# e.g., CHUNK_DETAIL_STORE, STRUCTURED_DATA_STORE from indexer.py

print("[State Module] Initialized shared state dictionaries.")