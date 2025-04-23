from fastapi import APIRouter, HTTPException, Depends

from app.models.api_models import AskRequest, AskResponse
# Import actual service functions
from app.services.knowledge.search import retrieve_context
from app.services.knowledge.llm_interface import generate_answer

router = APIRouter()

@router.post("/", response_model=AskResponse)
async def handle_ask_question(request: AskRequest):
    """
    Handles user questions: retrieves context, generates answer using LLM.
    """
    question = request.question.strip()
    session_id = request.session_id

    print(f"Received question: '{question}' for session: {session_id}")

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not session_id:
         raise HTTPException(status_code=400, detail="Session ID is missing.")

    # Optional: Check if session data exists (basic check using in-memory store)
    # In a real system, you might check a status field associated with the session_id
#    session_store = get_session_store(session_id)
    # if not session_store:
    #     print(f"Warning: No data found in store for session {session_id}. Maybe still processing or invalid ID?")
        # Depending on requirements, you might:
        # 1. Return an error immediately:
        #    raise HTTPException(status_code=404, detail=f"No data found or processed for session ID: {session_id}")
        # 2. Proceed anyway, retrieval will likely return empty context. Let's do this for simplicity now.

    try:
        # --- Call Dhaksesh's Search/Retrieval ---
        context_chunks = await retrieve_context(question, session_id)

        if not context_chunks:
            print(f"No relevant context found for session {session_id}.")
            # Even if no context, ask the LLM? Or return immediately?
            # Let's return "not_found" directly for clarity if retrieval fails.
            return AskResponse(
                answer="Could not find relevant information in the uploaded documents for this question.",
                type="not_found",
                sources=[]
            )

        # Get unique sources from the retrieved chunks
        sources = sorted(list(set(chunk.source for chunk in context_chunks)))

        # --- Call LLM Interface ---
        llm_result = await generate_answer(question, context_chunks)

        # Check if LLM call itself resulted in an error type
        if llm_result.get("type") == "error":
             raise HTTPException(status_code=500, detail=llm_result.get("answer", "LLM processing failed."))

        return AskResponse(
            answer=llm_result.get("answer", "Error: No answer content from LLM."),
            type=llm_result.get("type", "error"), # Should be set by generate_answer
            sources=sources, # Use sources derived from retrieved context
            data=llm_result.get("data"),
            chart_data=llm_result.get("chart_data")
        )

    except HTTPException as http_exc:
         raise http_exc # Re-raise FastAPI exceptions
    except Exception as e:
        print(f"CRITICAL ERROR handling question '{question}' for session {session_id}: {e}")
        import traceback
        traceback.print_exc() # Log full traceback for debugging
        raise HTTPException(status_code=500, detail=f"An internal server error occurred.")

