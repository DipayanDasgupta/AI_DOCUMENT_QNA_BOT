import faiss
import numpy as np
from typing import List, Dict, Optional

from app.models.data_models import DocumentChunk
from app.core.config import settings
from app.services.knowledge.indexer import _load_faiss_index, get_chunk_details, embed_model # Reuse embed model

async def retrieve_context(question: str, session_id: str, top_k: int = settings.SEARCH_TOP_K) -> List[DocumentChunk]:
    """
    Generates query embedding, searches the FAISS index for the session,
    and retrieves the corresponding full DocumentChunk details.
    """
    print(f"[Search Service] Retrieving context for '{question}' (Session: {session_id}, Top K: {top_k})")

    # 1. Load the index and mapping for the session
    load_result = _load_faiss_index(session_id)
    if not load_result:
        print(f"[Search Service] No index found for session {session_id}. Cannot search.")
        return []
    index, id_to_chunk_id_map = load_result

    if index.ntotal == 0:
         print(f"[Search Service] Index for session {session_id} is empty.")
         return []

    # 2. Generate embedding for the question
    try:
        print("[Search Service] Generating query embedding...")
        query_embedding = embed_model.encode([question], convert_to_numpy=True)
        print("[Search Service] Query embedding generated.")
    except Exception as e:
        print(f"[Search Service] ERROR generating query embedding: {e}")
        return []

    # 3. Search the FAISS index
    try:
        print(f"[Search Service] Searching index (size {index.ntotal}) for top {top_k} results...")
        # D = distances, I = indices (FAISS IDs)
        distances, indices = index.search(query_embedding.astype(np.float32), k=top_k)
        print(f"[Search Service] Search complete. Found indices: {indices}")

    except Exception as e:
        print(f"[Search Service] ERROR during FAISS search for session {session_id}: {e}")
        return []

    # 4. Retrieve chunk details using the mapping
    relevant_chunks = []
    if indices.size > 0:
        faiss_ids = indices[0] # Search returns results for each query embedding, we have only one
        for faiss_id in faiss_ids:
            if faiss_id == -1: # FAISS returns -1 for indices if k > ntotal or other issues
                continue
            chunk_id = id_to_chunk_id_map.get(faiss_id)
            if chunk_id:
                chunk_detail = get_chunk_details(session_id, chunk_id)
                if chunk_detail:
                    relevant_chunks.append(chunk_detail)
                else:
                    print(f"[Search Service] Warning: Found FAISS ID {faiss_id} but no corresponding chunk detail for chunk_id {chunk_id} in session {session_id}")
            else:
                print(f"[Search Service] Warning: Could not map FAISS ID {faiss_id} to chunk_id for session {session_id}")

    print(f"[Search Service] Retrieved {len(relevant_chunks)} relevant chunk details.")
    return relevant_chunks

