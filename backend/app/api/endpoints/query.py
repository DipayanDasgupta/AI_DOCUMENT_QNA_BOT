from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional, Any

from app.models.api_models import AskRequest, AskResponse
from app.services.knowledge.search import retrieve_context
from app.services.knowledge.llm_interface import generate_answer
from app.core.config import settings # Import settings

# Import Tavily client only if key exists
tavily_client = None
if settings.TAVILY_API_KEY:
    try:
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        print("[Query Endpoint] Tavily client initialized.")
    except ImportError:
        print("WARNING: tavily-python library not found. Web search disabled. Run: pip install tavily-python")
        tavily_client = None
    except Exception as e:
         print(f"ERROR initializing Tavily client: {e}")
         tavily_client = None
else:
     print("[Query Endpoint] TAVILY_API_KEY not set. Web search disabled.")


router = APIRouter()

async def perform_web_search(query: str) -> Optional[List[Dict[str, str]]]:
    """Performs a web search using Tavily if available."""
    if not tavily_client:
        return None
    print(f"[Web Search] Performing Tavily search for: {query}")
    try:
        # Use search_depth="basic" for faster results, "advanced" for more detail
        # max_results can be adjusted (default 5)
        response = tavily_client.search(query=query, search_depth="basic", max_results=5)
        # response structure is typically {"query": ..., "results": [{"title": ..., "url": ..., "content": ..., "score": ...}, ...]}
        results = response.get("results", [])
        print(f"[Web Search] Tavily returned {len(results)} results.")
        return results
    except Exception as e:
        print(f"[Web Search] ERROR during Tavily search: {e}")
        return None


@router.post("/", response_model=AskResponse)
async def handle_ask_question(request: AskRequest):
    """Handles questions: retrieves doc context, performs web search, generates answer."""
    question = request.question.strip()
    session_id = request.session_id
    print(f"Received question: '{question}' for session: {session_id}")

    if not question or not session_id: raise HTTPException(status_code=400, detail="Missing question or session_id.")

    web_search_results = None
    search_sources = set() # Use set for unique sources

    try:
        # --- 1. Retrieve Document Context ---
        context_chunks = await retrieve_context(question, session_id)
        if context_chunks:
            search_sources.update(chunk.source for chunk in context_chunks) # Add doc sources
            print(f"Retrieved {len(context_chunks)} chunks from documents.")
        else:
            print("No relevant context found in documents for this question.")

        # --- 2. Perform Web Search (Conditional) ---
        # Decide if web search is needed (e.g., no doc context, or question implies it)
        # Simple logic: Always search for now, LLM prompt prioritizes doc context
        if tavily_client: # Only search if client is available
             web_search_raw = await perform_web_search(question)
             if web_search_raw:
                 web_search_results = web_search_raw # Pass raw results for formatting later
                 search_sources.add("Web Search via Tavily") # Add web as a source

        # --- 3. Generate Answer using Combined Context ---
        # Pass both document chunks and raw web search results (list of dicts)
        llm_result = await generate_answer(question, context_chunks, web_search_results)

        # Check for LLM error before constructing final response
        if llm_result.get("type") == "error":
             # Maybe use HTTPException for internal errors?
             # For now, return as regular response with error type
             print(f"LLM generation failed: {llm_result.get('answer')}")
             # Fall through to return the error response structure

        # Construct final response
        return AskResponse(
            answer=llm_result.get("answer", "Error processing LLM response."),
            type=llm_result.get("type", "error"),
            sources=sorted(list(search_sources)) if llm_result.get("type") != "error" else [], # Provide sources unless error
            data=None, # Not implemented in this version
            chart_data=None # Not implemented in this version
        )

    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        print(f"CRITICAL ERROR handling question '{question}' for session {session_id}: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error processing question.")

