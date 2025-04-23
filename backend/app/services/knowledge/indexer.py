import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import json
import asyncio
from typing import List, Dict, Optional, Tuple

from app.models.data_models import DocumentChunk
from app.core.config import settings

# --- Globals ---
# Load embedding model once on startup (or lazy load on first use)
# Consider moving model loading to lifespan if memory usage is high
print(f"[Indexer Service] Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
# device = settings.EMBEDDING_DEVICE # Or let sentence-transformers auto-detect
embed_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME) # Add device=device if needed
EMBEDDING_DIM = embed_model.get_sentence_embedding_dimension()
print(f"[Indexer Service] Embedding model loaded. Dimension: {EMBEDDING_DIM}")

# Lock for managing potential concurrent access to index files (per session)
index_locks: Dict[str, asyncio.Lock] = {}

# --- Helper Functions ---

def _get_session_index_paths(session_id: str) -> Tuple[str, str]:
    """Returns the paths for the FAISS index and mapping file for a session."""
    index_file = os.path.join(settings.INDEX_DIR, f"{session_id}.faiss")
    mapping_file = os.path.join(settings.INDEX_DIR, f"{session_id}.json")
    return index_file, mapping_file

async def _get_lock(session_id: str) -> asyncio.Lock:
    """Gets or creates an asyncio Lock for a given session ID."""
    if session_id not in index_locks:
        index_locks[session_id] = asyncio.Lock()
    return index_locks[session_id]

def _load_faiss_index(session_id: str) -> Optional[Tuple[faiss.Index, Dict[int, str]]]:
    """Loads the FAISS index and ID->chunk_id mapping for a session."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    if not os.path.exists(index_file) or not os.path.exists(mapping_file):
        return None # Index doesn't exist

    try:
        print(f"[Indexer Service] Loading index for session: {session_id}")
        index = faiss.read_index(index_file)
        with open(mapping_file, 'r') as f:
            # Keys in JSON are strings, convert back to int for FAISS IDs
            mapping_str_keys = json.load(f)
            id_to_chunk_id_map = {int(k): v for k, v in mapping_str_keys.items()}
        print(f"[Indexer Service] Index loaded. Size: {index.ntotal}")
        return index, id_to_chunk_id_map
    except Exception as e:
        print(f"[Indexer Service] ERROR loading index for session {session_id}: {e}")
        return None

def _save_faiss_index(session_id: str, index: faiss.Index, id_to_chunk_id_map: Dict[int, str]):
    """Saves the FAISS index and ID->chunk_id mapping."""
    index_file, mapping_file = _get_session_index_paths(session_id)
    try:
        print(f"[Indexer Service] Saving index for session: {session_id} (Size: {index.ntotal})")
        faiss.write_index(index, index_file)
        # Keys in JSON must be strings
        mapping_str_keys = {str(k): v for k, v in id_to_chunk_id_map.items()}
        with open(mapping_file, 'w') as f:
            json.dump(mapping_str_keys, f)
        print(f"[Indexer Service] Index saved.")
    except Exception as e:
        print(f"[Indexer Service] ERROR saving index for session {session_id}: {e}")


# --- Main Indexing Logic ---

# Store chunk details in memory mapped by chunk_id for easy retrieval after search
# Structure: { session_id: { chunk_id: DocumentChunk } }
# WARNING: Still lost on restart! Needs persistent storage (DB, file) for production.
CHUNK_DETAIL_STORE: Dict[str, Dict[str, DocumentChunk]] = {}

async def index_content(content_chunks: List[DocumentChunk], session_id: str) -> bool:
    """
    Generates embeddings and adds content chunks to the FAISS index for the session.
    Saves the index and mappings to disk.
    """
    if not content_chunks:
        print("[Indexer Service] No content chunks received for indexing.")
        return True

    print(f"[Indexer Service] Starting indexing for {len(content_chunks)} chunks (Session: {session_id})")
    lock = await _get_lock(session_id)
    async with lock: # Acquire lock for this session's index operations
        # Load existing index or create a new one
        load_result = _load_faiss_index(session_id)
        if load_result:
            index, id_to_chunk_id_map = load_result
            next_id = index.ntotal # FAISS IDs are sequential 0 to ntotal-1
        else:
            print(f"[Indexer Service] Creating new index for session: {session_id}")
            index = faiss.IndexFlatL2(EMBEDDING_DIM) # Simple L2 distance index
            id_to_chunk_id_map = {}
            next_id = 0

        # Prepare chunk data for embedding
        texts_to_embed = [chunk.text for chunk in content_chunks]
        chunk_ids = [chunk.chunk_id for chunk in content_chunks] # Keep track of original chunk IDs

        try:
            print(f"[Indexer Service] Generating {len(texts_to_embed)} embeddings...")
            embeddings = embed_model.encode(texts_to_embed, convert_to_numpy=True)
            print("[Indexer Service] Embeddings generated.")

            if embeddings.shape[0] > 0:
                 # Add embeddings to FAISS index
                 index.add(embeddings.astype(np.float32)) # FAISS uses float32

                 # Update mapping and detail store
                 if session_id not in CHUNK_DETAIL_STORE:
                     CHUNK_DETAIL_STORE[session_id] = {}

                 for i, chunk in enumerate(content_chunks):
                     faiss_id = next_id + i
                     id_to_chunk_id_map[faiss_id] = chunk.chunk_id
                     # Store the full chunk details (without embedding to save memory if needed)
                     # Or store with embedding if retrieval needs it directly
                     CHUNK_DETAIL_STORE[session_id][chunk.chunk_id] = chunk

                 print(f"[Indexer Service] Added {embeddings.shape[0]} vectors to index. New total: {index.ntotal}")

                 # Save the updated index and mapping
                 _save_faiss_index(session_id, index, id_to_chunk_id_map)
                 return True
            else:
                 print("[Indexer Service] No embeddings generated (empty input?).")
                 return True # No failure, just nothing added

        except Exception as e:
            print(f"[Indexer Service] ERROR during embedding or indexing for session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return False

def get_chunk_details(session_id: str, chunk_id: str) -> Optional[DocumentChunk]:
    """Retrieves the full DocumentChunk details from the in-memory store."""
    session_store = CHUNK_DETAIL_STORE.get(session_id)
    if session_store:
        return session_store.get(chunk_id)
    return None

def get_session_chunk_count(session_id: str) -> int:
    """Gets the number of chunks stored in memory for a session (for checking existence)."""
    return len(CHUNK_DETAIL_STORE.get(session_id, {}))

async def clear_session_data(session_id: str):
    """Removes index files and in-memory data for a session."""
    print(f"[Indexer Service] Clearing data for session: {session_id}")
    lock = await _get_lock(session_id)
    async with lock:
        # Remove from in-memory stores
        if session_id in CHUNK_DETAIL_STORE:
            del CHUNK_DETAIL_STORE[session_id]
        if session_id in index_locks: # Remove the lock itself
             del index_locks[session_id]

        # Remove files from disk
        index_file, mapping_file = _get_session_index_paths(session_id)
        try:
            if os.path.exists(index_file):
                os.remove(index_file)
                print(f"[Indexer Service] Removed file: {index_file}")
            if os.path.exists(mapping_file):
                os.remove(mapping_file)
                print(f"[Indexer Service] Removed file: {mapping_file}")
        except OSError as e:
            print(f"[Indexer Service] ERROR removing index files for session {session_id}: {e}")
        print(f"[Indexer Service] Cleared data for session {session_id}")
        return True

