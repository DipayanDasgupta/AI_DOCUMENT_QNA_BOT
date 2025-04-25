import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import json
import asyncio
from typing import List, Dict, Optional, Tuple
import pandas as pd # Import pandas

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
     embed_model = None; EMBEDDING_DIM = 0 # Handle failure

index_locks: Dict[str, asyncio.Lock] = {}

# --- In-Memory Stores (WARNING: Lost on restart) ---
# Store chunk text/metadata details for retrieval after search
# Structure: { session_id: { chunk_id: DocumentChunk } }
CHUNK_DETAIL_STORE: Dict[str, Dict[str, DocumentChunk]] = {}

# Store loaded pandas DataFrames for structured files
# Structure: { session_id: { filename: pd.DataFrame } }
STRUCTURED_DATA_STORE: Dict[str, Dict[str, pd.DataFrame]] = {}
# ---------------------------------------------------------

# --- Helper Functions ---
def _get_session_index_paths(session_id: str) -> Tuple[str, str]:
    """Returns paths for FAISS index and mapping file."""
    index_file = os.path.join(settings.INDEX_DIR, f"{session_id}.faiss")
    mapping_file = os.path.join(settings.INDEX_DIR, f"{session_id}.json")
    return index_file, mapping_file

async def _get_lock(session_id: str) -> asyncio.Lock:
    """Gets or creates an asyncio Lock for a session."""
    if session_id not in index_locks: index_locks[session_id] = asyncio.Lock()
    return index_locks[session_id]

def _load_faiss_index(session_id: str) -> Optional[Tuple[faiss.Index, Dict[int, str]]]:
    """Loads FAISS index and ID->chunk_id mapping."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    if not os.path.exists(index_file) or not os.path.exists(mapping_file): return None
    try:
        print(f"[Indexer Service] Loading index for session: {session_id}")
        index = faiss.read_index(index_file); mapping_str_keys = json.load(open(mapping_file, 'r'))
        id_to_chunk_id_map = {int(k): v for k, v in mapping_str_keys.items()}
        print(f"[Indexer Service] Index loaded. Size: {index.ntotal}")
        return index, id_to_chunk_id_map
    except Exception as e: print(f"[Indexer Service] ERROR loading index for {session_id}: {e}"); return None

def _save_faiss_index(session_id: str, index: faiss.Index, id_to_chunk_id_map: Dict[int, str]):
    """Saves FAISS index and ID->chunk_id mapping."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    try:
        print(f"[Indexer Service] Saving index for {session_id} (Size: {index.ntotal})")
        faiss.write_index(index, index_file)
        mapping_str_keys = {str(k): v for k, v in id_to_chunk_id_map.items()}
        with open(mapping_file, 'w') as f: json.dump(mapping_str_keys, f)
        print(f"[Indexer Service] Index saved.")
    except Exception as e: print(f"[Indexer Service] ERROR saving index for {session_id}: {e}")

# --- Structured Data Storage ---
def store_structured_data(session_id: str, filename: str, df: pd.DataFrame):
    """Stores a DataFrame in the in-memory store."""
    if session_id not in STRUCTURED_DATA_STORE:
        STRUCTURED_DATA_STORE[session_id] = {}
    STRUCTURED_DATA_STORE[session_id][filename] = df
    print(f"[Indexer Service] Stored DataFrame for {filename} in session {session_id}")

def get_structured_data(session_id: str, filename: str) -> Optional[pd.DataFrame]:
    """Retrieves a stored DataFrame."""
    session_store = STRUCTURED_DATA_STORE.get(session_id)
    if session_store: return session_store.get(filename)
    return None

# --- Main Indexing Logic ---
async def index_content(content_chunks: List[DocumentChunk], session_id: str) -> bool:
    """Indexes text chunks (including summaries of structured data) into FAISS."""
    if not embed_model: print("ERROR: Embedding model not loaded. Cannot index."); return False
    if not content_chunks: print("[Indexer Service] No content chunks received for indexing."); return True

    print(f"[Indexer Service] Starting indexing for {len(content_chunks)} chunks (Session: {session_id})")
    lock = await _get_lock(session_id)
    async with lock:
        load_result = _load_faiss_index(session_id)
        if load_result: index, id_to_chunk_id_map = load_result; next_id = index.ntotal
        else: print(f"[Indexer Service] Creating new index for session: {session_id}"); index = faiss.IndexFlatL2(EMBEDDING_DIM); id_to_chunk_id_map = {}; next_id = 0

        texts_to_embed = [chunk.text for chunk in content_chunks]
        chunk_ids = [chunk.chunk_id for chunk in content_chunks]

        try:
            print(f"[Indexer Service] Generating {len(texts_to_embed)} embeddings...")
            embeddings = embed_model.encode(texts_to_embed, convert_to_numpy=True, show_progress_bar=False) # Disable progress bar for logs
            print("[Indexer Service] Embeddings generated.")

            if embeddings.shape[0] > 0:
                 index.add(embeddings.astype(np.float32))
                 if session_id not in CHUNK_DETAIL_STORE: CHUNK_DETAIL_STORE[session_id] = {}
                 for i, chunk in enumerate(content_chunks):
                     faiss_id = next_id + i; id_to_chunk_id_map[faiss_id] = chunk.chunk_id
                     CHUNK_DETAIL_STORE[session_id][chunk.chunk_id] = chunk # Store details
                 print(f"[Indexer Service] Added {embeddings.shape[0]} vectors. New total: {index.ntotal}")
                 _save_faiss_index(session_id, index, id_to_chunk_id_map)
                 return True
            else: print("[Indexer Service] No embeddings generated (empty input?)."); return True

        except Exception as e:
            print(f"[Indexer Service] ERROR during embedding/indexing for {session_id}: {e}"); traceback.print_exc(); return False

# --- Retrieval and Cleanup ---
def get_chunk_details(session_id: str, chunk_id: str) -> Optional[DocumentChunk]:
    """Retrieves full DocumentChunk details from memory."""
    session_store = CHUNK_DETAIL_STORE.get(session_id)
    if session_store: return session_store.get(chunk_id)
    return None

async def clear_session_data(session_id: str):
    """Removes index files and in-memory data for a session."""
    print(f"[Indexer Service] Clearing data for session: {session_id}")
    lock = await _get_lock(session_id)
    async with lock:
        if session_id in CHUNK_DETAIL_STORE: del CHUNK_DETAIL_STORE[session_id]
        if session_id in STRUCTURED_DATA_STORE: del STRUCTURED_DATA_STORE[session_id] # Clear structured data too
        if session_id in index_locks: del index_locks[session_id]

        index_file, mapping_file = _get_session_index_paths(session_id)
        try:
            if os.path.exists(index_file): os.remove(index_file); print(f"[Indexer Service] Removed file: {index_file}")
            if os.path.exists(mapping_file): os.remove(mapping_file); print(f"[Indexer Service] Removed file: {mapping_file}")
        except OSError as e: print(f"[Indexer Service] ERROR removing index files for {session_id}: {e}")
        print(f"[Indexer Service] Cleared data for session {session_id}")
        return True

