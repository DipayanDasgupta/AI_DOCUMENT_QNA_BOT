import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import json
import asyncio
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import traceback

from app.models.data_models import DocumentChunk
from app.core.config import settings

# --- Globals ---
print(f"[Indexer Service] Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
try:
    embed_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    EMBEDDING_DIM = embed_model.get_sentence_embedding_dimension()
    print(f"[Indexer Service] Embedding model loaded. Dimension: {EMBEDDING_DIM}")
except Exception as e:
     print(f"FATAL ERROR: Failed to load embedding model '{settings.EMBEDDING_MODEL_NAME}': {e}")
     embed_model = None; EMBEDDING_DIM = 0

index_locks: Dict[str, asyncio.Lock] = {}

# --- In-Memory Store for DataFrames ONLY (Text Chunks are now persisted with index) ---
# Structure: { session_id: { filename: pd.DataFrame } }
STRUCTURED_DATA_STORE: Dict[str, Dict[str, pd.DataFrame]] = {}
# --- CHUNK_DETAIL_STORE REMOVED ---
# -----------------------------------------------------------------------------------

# --- Helper Functions ---
def _get_session_index_paths(session_id: str) -> Tuple[str, str]:
    """Returns paths for FAISS index and the NEW chunk data mapping file."""
    index_file = os.path.join(settings.INDEX_DIR, f"{session_id}.faiss")
    # Mapping file now stores chunk data directly mapped to FAISS ID
    mapping_file = os.path.join(settings.INDEX_DIR, f"{session_id}_chunk_data.json")
    return index_file, mapping_file

async def _get_lock(session_id: str) -> asyncio.Lock:
    """Gets or creates an asyncio Lock for a session."""
    # Need a lock per session to prevent race conditions on file save/load
    global index_locks
    if session_id not in index_locks:
        index_locks[session_id] = asyncio.Lock()
    return index_locks[session_id]

# --- Load Function Modified ---
def _load_faiss_index_and_data(session_id: str) -> Optional[Tuple[faiss.Index, Dict[int, Dict[str, Any]]]]:
    """Loads FAISS index and ID->ChunkData mapping for a session."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    if not os.path.exists(index_file) or not os.path.exists(mapping_file):
        print(f"[Indexer Service Load] Index or mapping file missing for session: {session_id}")
        return None # Index doesn't exist or is incomplete

    try:
        print(f"[Indexer Service Load] Loading index and chunk data for session: {session_id}")
        index = faiss.read_index(index_file)
        with open(mapping_file, 'r', encoding='utf-8') as f:
            # Keys in JSON are strings, convert back to int for FAISS IDs
            mapping_str_keys: Dict[str, Dict[str, Any]] = json.load(f)
            id_to_chunk_data_map: Dict[int, Dict[str, Any]] = {int(k): v for k, v in mapping_str_keys.items()}
        print(f"[Indexer Service Load] Index loaded (Size: {index.ntotal}), Mapping loaded ({len(id_to_chunk_data_map)} items).")
        # Sanity check
        if index.ntotal != len(id_to_chunk_data_map):
             print(f"[Indexer Service Load] WARNING: Index size ({index.ntotal}) != Mapping size ({len(id_to_chunk_data_map)}) for session {session_id}!")
             # Decide how to handle this - maybe return None or try to proceed? Returning None is safer.
             # return None
        return index, id_to_chunk_data_map
    except FileNotFoundError:
        print(f"[Indexer Service Load] File not found during load for session {session_id}")
        return None
    except Exception as e:
        print(f"[Indexer Service Load] ERROR loading index/data for session {session_id}: {e}")
        traceback.print_exc()
        return None

# --- Save Function Modified ---
def _save_faiss_index_and_data(session_id: str, index: faiss.Index, id_to_chunk_data_map: Dict[int, Dict[str, Any]]):
    """Saves FAISS index and ID->ChunkData mapping."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    try:
        print(f"[Indexer Service Save] Saving index for {session_id} (Size: {index.ntotal})")
        faiss.write_index(index, index_file)

        print(f"[Indexer Service Save] Saving chunk data mapping for {session_id} ({len(id_to_chunk_data_map)} items)")
        # Keys in JSON must be strings
        mapping_str_keys = {str(k): v for k, v in id_to_chunk_data_map.items()}
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping_str_keys, f, ensure_ascii=False, indent=2) # Use indent for readability
        print(f"[Indexer Service Save] Index and mapping saved successfully.")
    except Exception as e:
        print(f"[Indexer Service Save] ERROR saving index/data for session {session_id}: {e}")
        traceback.print_exc()


# --- Structured Data Storage ---
def store_structured_data(session_id: str, filename: str, df: pd.DataFrame):
    """Stores a DataFrame in the in-memory store."""
    if session_id not in STRUCTURED_DATA_STORE: STRUCTURED_DATA_STORE[session_id] = {}
    STRUCTURED_DATA_STORE[session_id][filename] = df
    print(f"[Indexer Service] Stored DataFrame for {filename} in session {session_id}")

def get_structured_data(session_id: str, filename: str) -> Optional[pd.DataFrame]:
    """Retrieves a stored DataFrame."""
    session_store = STRUCTURED_DATA_STORE.get(session_id)
    if session_store: return session_store.get(filename)
    return None

# --- Main Indexing Logic Modified ---
async def index_content(content_chunks: List[DocumentChunk], session_id: str) -> bool:
    """Generates embeddings and adds chunks + metadata to FAISS index & mapping file."""
    if not embed_model: print("ERROR: Embedding model not loaded. Cannot index."); return False
    if not content_chunks: print("[Indexer Service] No content chunks received for indexing."); return True

    print(f"[Indexer Service] Starting indexing for {len(content_chunks)} chunks (Session: {session_id})")
    lock = await _get_lock(session_id)
    async with lock: # Acquire lock for file operations
        # Load existing index/data or create new ones
        load_result = _load_faiss_index_and_data(session_id)
        if load_result: index, id_to_chunk_data_map = load_result; next_id = index.ntotal
        else: print(f"[Indexer Service] Creating new index & mapping for session: {session_id}"); index = faiss.IndexFlatL2(EMBEDDING_DIM); id_to_chunk_data_map = {}; next_id = 0

        texts_to_embed = [chunk.text for chunk in content_chunks]

        try:
            print(f"[Indexer Service] Generating {len(texts_to_embed)} embeddings...")
            embeddings = embed_model.encode(texts_to_embed, convert_to_numpy=True, show_progress_bar=False)
            print("[Indexer Service] Embeddings generated.")

            if embeddings.shape[0] > 0:
                 print(f"[Indexer Service] Adding {embeddings.shape[0]} vectors to FAISS index...")
                 index.add(embeddings.astype(np.float32))

                 # Populate the id_to_chunk_data_map with essential data for retrieval
                 print(f"[Indexer Service] Populating chunk data mapping...")
                 for i, chunk in enumerate(content_chunks):
                     faiss_id = next_id + i
                     # Store dictionary representation of essential chunk data
                     id_to_chunk_data_map[faiss_id] = {
                         "chunk_id": chunk.chunk_id, # Keep chunk_id if needed elsewhere
                         "text": chunk.text,
                         "source": chunk.source,
                         "page": chunk.page,
                         "metadata": chunk.metadata,
                     }
                 print(f"[Indexer Service] Added {embeddings.shape[0]} items to mapping. New index total: {index.ntotal}")

                 # Save the updated index and the NEW chunk data mapping
                 _save_faiss_index_and_data(session_id, index, id_to_chunk_data_map)
                 return True
            else: print("[Indexer Service] No embeddings generated."); return True

        except Exception as e:
            print(f"[Indexer Service] ERROR during embedding/indexing for {session_id}: {e}"); traceback.print_exc(); return False

# --- get_chunk_details REMOVED ---

# --- Cleanup Modified ---
async def clear_session_data(session_id: str):
    """Removes index/mapping files and in-memory structured data for a session."""
    print(f"[Indexer Service] Clearing data for session: {session_id}")
    lock = await _get_lock(session_id) # Use lock for file removal too
    async with lock:
        # Remove from in-memory stores first
        if session_id in STRUCTURED_DATA_STORE: del STRUCTURED_DATA_STORE[session_id]
        if session_id in index_locks: del index_locks[session_id] # Remove lock itself after use

        # Remove files from disk
        index_file, mapping_file = _get_session_index_paths(session_id)
        removed_files = []
        try:
            if os.path.exists(index_file): os.remove(index_file); removed_files.append(index_file)
            if os.path.exists(mapping_file): os.remove(mapping_file); removed_files.append(mapping_file)
            if removed_files: print(f"[Indexer Service] Removed files: {', '.join(removed_files)}")
        except OSError as e: print(f"[Indexer Service] ERROR removing index/mapping files for {session_id}: {e}")
        print(f"[Indexer Service] Cleared data processing complete for session {session_id}")
        return True

