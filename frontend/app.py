# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import json
import os
import time
import asyncio

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/upload"
ASK_ENDPOINT = f"{BACKEND_URL}/api/v1/ask"
STATUS_ENDPOINT = f"{BACKEND_URL}/api/v1/status"

# --- Set Page Config FIRST ---
st.set_page_config(page_title="Mando AI Document Q&A", layout="wide", initial_sidebar_state="expanded")

# --- Custom CSS ---
st.markdown("""<style>...</style>""", unsafe_allow_html=True) # Keep your existing CSS

# --- Helper Functions ---
def display_sources(sources):
    if sources:
        with st.expander("View Sources", expanded=False):
            st.markdown(f"**Answer derived from ({len(sources)} sources):**")
            for i, source in enumerate(sources): st.caption(f"- {source}")

def check_backend_status(session_id):
    # ... (keep existing check_backend_status function) ...
    if not session_id: return None
    try:
        status_url = f"{STATUS_ENDPOINT}/{session_id}"
        print(f"Frontend: Checking status at {status_url}") # DEBUG
        response = requests.get(status_url, timeout=15) # Increased timeout slightly
        response.raise_for_status()
        status_data = response.json()
        print(f"Frontend: Status received: {status_data}") # DEBUG
        return status_data
    except requests.exceptions.Timeout: print("Frontend: Status check timed out."); return {"status": "timeout", "message": "Status check timed out."}
    except requests.exceptions.RequestException as e:
        print(f"Frontend: Status check failed: {e}")
        status_code = e.response.status_code if hasattr(e, 'response') else 500
        if status_code == 404: return {"status": "not_found", "message": "Session ID not found."}
        else: return {"status": "error", "message": f"Status check request failed: {e}"}

# --- Streamlit App ---
st.title("📄 AI Document Q&A System")
st.markdown("Upload documents. Processing includes OCR & Web Crawling.")

# --- Session State Init ---
if "session_id" not in st.session_state: st.session_state.session_id = None
if "processing_complete" not in st.session_state: st.session_state.processing_complete = False
if "status_message" not in st.session_state: st.session_state.status_message = "" # Combined status message
if "is_processing" not in st.session_state: st.session_state.is_processing = False # Simpler flag for polling
if "messages" not in st.session_state: st.session_state.messages = []
if "uploaded_file_names" not in st.session_state: st.session_state.uploaded_file_names = []

# --- Sidebar ---
with st.sidebar:
    st.header("Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files", accept_multiple_files=True,
        type=["pdf", "docx", "pptx", "xlsx", "csv", "json", "txt", "png", "jpg", "jpeg"],
        key="file_uploader"
    )
    current_file_names = sorted([f.name for f in uploaded_files]) if uploaded_files else []

    # --- Upload Logic ---
    if current_file_names != st.session_state.uploaded_file_names:
        print(f"Frontend: File change detected. Old: {st.session_state.uploaded_file_names}, New: {current_file_names}")
        # Reset state for new upload
        st.session_state.session_id = None
        st.session_state.processing_complete = False
        st.session_state.messages = []
        st.session_state.uploaded_file_names = current_file_names
        st.session_state.status_message = ""
        st.session_state.is_processing = False

        if uploaded_files:
            st.session_state.status_message = f"Uploading {len(uploaded_files)} file(s)..."
            st.session_state.is_processing = True # Assume processing starts now
            # Display initial uploading message immediately
            st.info(st.session_state.status_message, icon="⏳")

            with st.spinner("Uploading..."): # Spinner only for the actual POST request
                files_to_send = []
                for up_file in uploaded_files: files_to_send.append(("files", (up_file.name, up_file.getvalue(), up_file.type)))

                try:
                    print(f"Frontend: Sending POST to {UPLOAD_ENDPOINT}")
                    response = requests.post(UPLOAD_ENDPOINT, files=files_to_send, timeout=60) # Generous timeout
                    print(f"Frontend: Initial upload response status: {response.status_code}")
                    response.raise_for_status()
                    result = response.json()
                    print(f"Frontend: Initial upload response JSON: {result}")

                    session_id_received = result.get("session_id")
                    backend_status = result.get("status")

                    if session_id_received and backend_status == "processing":
                        st.session_state.session_id = session_id_received
                        st.session_state.status_message = result.get("message", "Processing started...")
                        st.session_state.is_processing = True # Confirm processing state
                        print(f"Frontend: Upload successful, Session: {session_id_received}. Polling should start.")
                    else: # Failed to get session_id or 'processing' status
                        raise ValueError(f"Backend did not confirm processing start. Response: {result}")

                except Exception as e:
                    print(f"Frontend: Upload POST failed: {e}")
                    st.session_state.status_message = f"❌ Upload failed: {e}"
                    st.session_state.is_processing = False # Stop processing state on failure
                    st.session_state.session_id = None # Ensure session_id is cleared

            # Rerun AFTER the upload attempt to display status/start polling check
            print("Frontend: Rerunning after upload attempt...")
            st.rerun()

        # Handle case where files are removed (uploader becomes empty)
        elif not uploaded_files:
             print("Frontend: Files removed.")
             # State was already reset above
             st.session_state.status_message = "Upload documents to begin."
             st.rerun() # Rerun to clear old status messages if any

    # --- Status Display & Polling ---
    status_container = st.container() # Use a container to manage status display area
    if st.session_state.get('is_processing', False):
        with status_container:
            st.info(st.session_state.get('status_message', 'Processing...'), icon="⏳")

        # Perform status check
        status_result = check_backend_status(st.session_state.get('session_id'))

        if status_result:
            current_status = status_result.get("status")
            current_message = status_result.get("message")

            if current_status == "ready":
                print(f"Frontend: Polling SUCCESS - Status 'ready' for session {st.session_state.session_id}")
                st.session_state.processing_complete = True
                st.session_state.is_processing = False
                st.session_state.status_message = current_message or "✅ Processing complete!"
                st.success(st.session_state.status_message, icon="✅") # Show final success
                time.sleep(0.5) # Brief pause before final rerun
                st.rerun()
            elif current_status == "error":
                print(f"Frontend: Polling FAILURE - Status 'error' for session {st.session_state.session_id}")
                st.session_state.processing_complete = False
                st.session_state.is_processing = False
                st.session_state.status_message = f"❌ Processing failed: {current_message or 'Unknown backend error.'}"
                st.error(st.session_state.status_message, icon="❌") # Show final error
                # No rerun here, processing stopped
            elif current_status == "processing":
                # Update message if backend provided a new one
                if current_message and current_message != st.session_state.get('status_message'):
                    st.session_state.status_message = current_message
                    # Rerun will update the st.info message
                print(f"Frontend: Polling - Status 'processing'. Message: {current_message}. Will check again...")
                time.sleep(4) # Poll every 4 seconds
                st.rerun()
            else: # timeout, not_found, etc.
                print(f"Frontend: Polling WARNING - Status '{current_status}' for {st.session_state.session_id}")
                st.session_state.status_message = f"⚠️ Status check issue: {current_message or current_status}"
                st.session_state.is_processing = False # Stop polling
                st.warning(st.session_state.status_message, icon="⚠️")
                # No rerun here, processing stopped
        else: # check_backend_status returned None (e.g., initial state)
             print(f"Frontend: Status check invalid for {st.session_state.session_id}. Stopping poll.")
             st.session_state.is_processing = False # Ensure polling stops
             # Potentially add a warning message here
             st.warning("Could not verify processing status.", icon="⚠️")

    # --- Display final status if processing finished ---
    elif not st.session_state.get('is_processing', False) and st.session_state.get('status_message'):
         # Display final success/error/warning messages if polling is complete
         status_type = "info" # Default
         if "✅" in st.session_state.status_message: status_type = "success"
         elif "❌" in st.session_state.status_message: status_type = "error"
         elif "⚠️" in st.session_state.status_message: status_type = "warning"

         with status_container:
             if status_type == "success": st.success(st.session_state.status_message, icon="✅")
             elif status_type == "error": st.error(st.session_state.status_message, icon="❌")
             elif status_type == "warning": st.warning(st.session_state.status_message, icon="⚠️")
             # else: st.info(st.session_state.status_message) # Don't show initial "upload..." after completion

    # --- Display Uploaded Files Expander ---
    if st.session_state.get('session_id') and st.session_state.get('uploaded_file_names'):
        expander_title = "Uploaded Files"
        status_icon = ""
        is_ready = st.session_state.get('processing_complete', False)
        is_error = "❌" in st.session_state.get('status_message', '')

        if st.session_state.get('is_processing', False): expander_title += " (Processing...)"; status_icon="⏳"
        elif is_ready and not is_error: expander_title += " (Ready)"; status_icon="✅"
        elif is_error: expander_title += " (Error)"; status_icon="❌"

        with st.expander(f"{status_icon} {expander_title}", expanded=True):
            for name in st.session_state.get('uploaded_file_names', []): st.caption(name)

    # --- Clear Session Button ---
    st.markdown("---")
    if st.button("Clear Session & Start Over", key="clear_session"):
        print("Frontend: Clearing session state.")
        st.session_state.clear()
        st.rerun()

    st.markdown("---"); st.caption(f"Backend API: {BACKEND_URL}")


# --- Chat Interface ---
message_container = st.container()
with message_container:
    # Display chat messages from history
    for message in st.session_state.get('messages', []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                display_sources(message["sources"])

# Chat input - disable based on processing_complete state
prompt = st.chat_input("Ask a question...", disabled=not st.session_state.get('processing_complete', False), key="chat_input")

if prompt:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt: st.warning("Please enter a question.")
    elif not st.session_state.get('session_id'): st.error("Session ID missing.")
    else:
        # Add user message state and immediately display in container
        st.session_state.messages.append({"role": "user", "content": cleaned_prompt, "type": "text"})
        with message_container:
             with st.chat_message("user"): st.markdown(cleaned_prompt)

        # Get response from backend
        with st.spinner("Thinking..."):
            full_response_content = ""; sources = []; response_type = "error"; response_data = None
            try:
                payload = {"question": cleaned_prompt, "session_id": st.session_state.session_id}
                print(f"Frontend: Sending POST to {ASK_ENDPOINT} with payload: {payload}")
                response = requests.post(ASK_ENDPOINT, json=payload, timeout=180)
                response.raise_for_status()
                result = response.json()
                print(f"Frontend: Raw backend response for /ask: {result}")

                full_response_content = result.get("answer", "Error: No answer field.")
                response_type = result.get("type", "error")
                sources = result.get("sources", [])

            except Exception as e:
                error_msg = f"❌ Error asking question: {e}"
                try: error_details = response.json().get("detail", response.text)
                except Exception: error_details = "(Could not parse backend error details)"
                error_msg += f"\nBackend: {error_details}\nStatus code: {response.status_code if 'response' in locals() else 'N/A'}"
                full_response_content = error_msg # Set error content

            # Add assistant response (success or error) to state
            st.session_state.messages.append({
                "role": "assistant", "content": full_response_content, "type": response_type,
                "data": None, "chart_data": None,
                "sources": sources if response_type != "error" else []
            })
        # Rerun to display the new assistant message from state
        st.rerun()
