import faiss
import numpy as np
from typing import List, Dict, Optional, Any

from app.models.data_models import DocumentChunk
from app.core.config import settings
# Import the loader function and embed model from indexer
from app.services.knowledge.indexer import _load_faiss_index_and_data, embed_model

async def retrieve_context(question: str, session_id: str, top_k: int = settings.SEARCH_TOP_K) -> List[DocumentChunk]:
    """
    Generates query embedding, searches FAISS index, retrieves chunk data from mapping file.
    """
    print(f"[Search Service] Retrieving context for '{question}' (Session: {session_id}, Top K: {top_k})")

    if not embed_model:
        print("ERROR: Embedding model not loaded. Cannot perform search.")
        return []

    # 1. Load the index AND the chunk data mapping
    load_result = _load_faiss_index_and_data(session_id)
    if not load_result:
        print(f"[Search Service] Index/mapping not found or failed to load for session {session_id}.")
        return []
    index, id_to_chunk_data_map = load_result

    if index.ntotal == 0:
         print(f"[Search Service] Index for session {session_id} is empty.")
         return []

    # 2. Generate query embedding
    try:
        print("[Search Service] Generating query embedding...")
        query_embedding = embed_model.encode([question], convert_to_numpy=True, show_progress_bar=False)
        print("[Search Service] Query embedding generated.")
    except Exception as e:
        print(f"[Search Service] ERROR generating query embedding: {e}")
        return []

    # 3. Search the FAISS index
    try:
        print(f"[Search Service] Searching index (size {index.ntotal}) for top {top_k} results...")
        distances, faiss_ids = index.search(query_embedding.astype(np.float32), k=min(top_k, index.ntotal)) # Search for k or ntotal if smaller
        print(f"[Search Service] Search complete. Found indices: {faiss_ids}")

    except Exception as e:
        print(f"[Search Service] ERROR during FAISS search for session {session_id}: {e}")
        return []

    # 4. Retrieve chunk data DIRECTLY from the loaded mapping
    relevant_chunks = []
    if faiss_ids.size > 0:
        retrieved_ids = faiss_ids[0] # Results for the first (only) query vector
        print(f"[Search Service] Processing retrieved FAISS IDs: {retrieved_ids}")
        for faiss_id in retrieved_ids:
            if faiss_id == -1: continue # Skip invalid IDs

            chunk_data = id_to_chunk_data_map.get(faiss_id) # Look up data using FAISS ID
            if chunk_data:
                try:
                    # Reconstruct DocumentChunk object from the retrieved dictionary
                    # Use .get() for potentially missing keys like 'page' or 'metadata'
                    chunk_obj = DocumentChunk(
                        session_id=session_id, # Add session_id back if needed downstream
                        chunk_id=chunk_data.get("chunk_id", f"faiss_{faiss_id}"), # Use original or generate one
                        text=chunk_data.get("text", ""),
                        source=chunk_data.get("source", "Unknown Source"),
                        page=chunk_data.get("page"),
                        metadata=chunk_data.get("metadata", {}),
                        # Embedding is not stored in the map, don't include it here
                    )
                    relevant_chunks.append(chunk_obj)
                except Exception as deser_err:
                     print(f"[Search Service] ERROR reconstructing DocumentChunk for FAISS ID {faiss_id}: {deser_err}")
            else:
                print(f"[Search Service] Warning: Could not find chunk data in mapping for FAISS ID {faiss_id} (Session: {session_id})")

    print(f"[Search Service] Retrieved {len(relevant_chunks)} relevant chunk details from mapping.")
    # --- get_chunk_details call REMOVED ---
    return relevant_chunks

