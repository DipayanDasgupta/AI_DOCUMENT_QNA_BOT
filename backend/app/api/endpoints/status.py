# backend/app/api/endpoints/status.py
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

# Import the shared status store from the dedicated state module
from app.core.state import session_status_store

router = APIRouter()

@router.get("/{session_id}", response_model=Dict[str, str])
async def get_session_status(session_id: str):
    """
    Checks the processing status for a given session ID.
    """
    print(f"[Status Endpoint] Checking status for session: {session_id}")
    # Access the imported dictionary
    session_info = session_status_store.get(session_id)

    if not session_info:
        print(f"[Status Endpoint] Session not found or status not yet set: {session_id}")
        # Return processing until the background task explicitly sets 'ready' or 'error'
        return {"status": "processing", "message": "Status unknown or processing..."}

    # If session_info WAS found:
    print(f"[Status Endpoint] Status for {session_id}: {session_info}")
    return session_info