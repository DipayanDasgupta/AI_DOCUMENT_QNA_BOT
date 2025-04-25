# backend/app/api/endpoints/query.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional, Any
import pandas as pd
import re # For simple keyword matching
import traceback
import json # Added for direct calc result formatting

from app.models.api_models import AskRequest, AskResponse
from app.services.knowledge.search import retrieve_context
# === ADDED format_context to the import ===
from app.services.knowledge.llm_interface import generate_answer, format_context
# ==========================================
from app.services.knowledge.indexer import get_structured_data # Import function to get stored DataFrame
from app.core.config import settings

# --- Tavily Client Initialization ---
tavily_client = None
if settings.TAVILY_API_KEY:
    try: from tavily import TavilyClient; tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY); print("[Query Endpoint] Tavily client OK.")
    except ImportError: print("WARN: tavily-python not found."); tavily_client = None
    except Exception as e: print(f"ERROR initializing Tavily: {e}"); tavily_client = None
else: print("[Query Endpoint] Tavily key not set.")

router = APIRouter()

# --- Helper for Web Search ---
async def perform_web_search(query: str) -> Optional[List[Dict[str, str]]]:
    if not tavily_client: return None
    print(f"[Web Search] Performing Tavily search for: {query}")
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=5)
        results = response.get("results", [])
        print(f"[Web Search] Tavily returned {len(results)} results.")
        return results
    except Exception as e: print(f"[Web Search] ERROR: {e}"); return None

# --- Helper for Direct Calculation (Placeholder Implementation) ---
def _attempt_direct_calculation(question: str, session_id: str) -> Optional[str]:
    """
    Analyzes question and attempts direct calculation on stored DataFrames.
    Returns a formatted string result if successful, otherwise None.
    NOTE: This is a basic placeholder. Robust implementation requires NLP/parsing.
    """
    q_lower = question.lower()
    calculation_result_str = None
    df_source_name = None # Identify which DataFrame is relevant

    # --- TODO: Implement logic to identify relevant DataFrame filename ---
    # Example: If question mentions specific filenames or keywords related to tables
    # A simple approach for now: Find the *first* stored DF for the session if question seems calc-related
    if "how many" in q_lower or "total" in q_lower or "average" in q_lower or "count" in q_lower or "list" in q_lower:
         from app.services.knowledge.indexer import STRUCTURED_DATA_STORE # Access store directly (alternative to get func)
         session_dfs = STRUCTURED_DATA_STORE.get(session_id, {})
         if session_dfs:
             df_source_name = next(iter(session_dfs.keys())) # Get the first filename found
             print(f"[Calc] Identified potentially relevant DataFrame: {df_source_name}")
         else:
              print("[Calc] Question seems calculation-related, but no DataFrames found in store.")


    if not df_source_name:
         # print("[Calc] No specific structured data source identified in query for calculation.")
         return None

    # Try to retrieve the DataFrame
    df = get_structured_data(session_id, df_source_name)
    if df is None:
        print(f"[Calc] DataFrame '{df_source_name}' could not be retrieved from store for session {session_id}.")
        return None

    print(f"[Calc] Attempting calculation on DataFrame: {df_source_name} (Shape: {df.shape})")

    # --- TODO: Implement More Robust Keyword/Intent Matching and Calculation ---
    try:
        if ("how many" in q_lower or "count" in q_lower or "total" in q_lower) and ("students" in q_lower or "entries" in q_lower or "rows" in q_lower):
            count = len(df)
            calculation_result_str = f"Direct Calculation ({df_source_name}): Total entries/rows found = {count}."
            # Note: Cannot reliably detect header row without more info

        elif ("how many male" in q_lower or "how many female" in q_lower or "gender count" in q_lower or ("count" in q_lower and "gender" in q_lower)):
            # Check if 'Gender' column exists (case-insensitive check)
            gender_col = next((col for col in df.columns if col.strip().lower() == 'gender'), None)
            if gender_col:
                 gender_counts = df[gender_col].value_counts().to_dict()
                 calculation_result_str = f"Direct Calculation ({df_source_name}): Gender counts = {json.dumps(gender_counts)}."
            else: calculation_result_str = f"Direct Calculation ({df_source_name}): 'Gender' column not found."

        # Add more rules here...
        # elif "total sales" in q_lower and 'Sales' in df.columns:
        #     total = df['Sales'].sum()
        #     calculation_result_str = f"Direct Calculation ({df_source_name}): Total Sales = {total}."

        else:
            print("[Calc] Question did not match simple calculation patterns.")

    except Exception as calc_err:
         print(f"[Calc] Error during direct calculation attempt: {calc_err}")
         traceback.print_exc()
         calculation_result_str = None # Fail silently, let LLM handle it

    if calculation_result_str:
        print(f"[Calc] Result: {calculation_result_str}")

    return calculation_result_str


# --- Main Query Endpoint ---
@router.post("/", response_model=AskResponse)
async def handle_ask_question(request: AskRequest):
    question = request.question.strip(); session_id = request.session_id
    print(f"Received question: '{question}' for session: {session_id}")
    if not question or not session_id: raise HTTPException(400, "Missing question or session_id.")

    direct_calc_result: Optional[str] = None
    web_search_results: Optional[List[Dict]] = None
    doc_context_chunks: List[DocumentChunk] = []
    search_sources = set()

    try:
        # --- 1. Attempt Direct Calculation ---
        direct_calc_result = _attempt_direct_calculation(question, session_id)
        if direct_calc_result: search_sources.add("Direct Calculation from Structured Data")

        # --- 2. Retrieve Document Context ---
        doc_context_chunks = await retrieve_context(question, session_id)
        if doc_context_chunks:
            search_sources.update(chunk.source for chunk in doc_context_chunks); print(f"Retrieved {len(doc_context_chunks)} doc chunks.")
        else: print("No relevant document context found.")

        # --- 3. Perform Web Search ---
        if tavily_client:
             web_search_raw = await perform_web_search(question)
             if web_search_raw: web_search_results = web_search_raw; search_sources.add("Web Search via Tavily")

        # --- 4. Prepare Context for LLM ---
        # Use the IMPORTED format_context function
        final_doc_context_str = format_context(doc_context_chunks) # <--- FIXED IMPORT
        if direct_calc_result:
            print("[Query] Prepending direct calculation result to context.")
            # Add the calculation result prominently
            final_doc_context_str = f"Direct Calculation Result: {direct_calc_result}\n\n---\n\n{final_doc_context_str}".strip()

        # --- 5. Generate Answer ---
        # Pass the formatted string context and web results to LLM
        # Note: The llm_interface needs the formatted strings, not the chunk objects directly for its prompt structure
        # We pass the chunk objects here mainly for source tracking later if needed, but the prompt uses the formatted strings.
        llm_result = await generate_answer(question, doc_context_chunks, web_search_results) # Pass original chunks for potential source tracking

        if llm_result.get("type") == "error": print(f"LLM generation failed: {llm_result.get('answer')}")

        # Return final response
        return AskResponse(
            answer=llm_result.get("answer", "Error processing LLM response."),
            type=llm_result.get("type", "error"),
            sources=sorted(list(search_sources)) if llm_result.get("type") != "error" else [],
            data=None, chart_data=None
        )

    except HTTPException as http_exc: raise http_exc
    except Exception as e: print(f"CRITICAL ERROR handling question '{question}': {e}"); traceback.print_exc(); raise HTTPException(500,"Internal server error.")