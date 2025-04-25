# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import json
import os
import time
import traceback # For better error logging in frontend

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/upload"
ASK_ENDPOINT = f"{BACKEND_URL}/api/v1/ask"
STATUS_ENDPOINT = f"{BACKEND_URL}/api/v1/status"

# --- Set Page Config FIRST ---
# Must be the first Streamlit command executed
st.set_page_config(page_title="Mando AI Document Q&A", layout="wide", initial_sidebar_state="expanded")

# --- Custom CSS ---
# Simple styling for chat messages
st.markdown("""
<style>
    /* Style for user messages */
    div[data-testid="stChatMessage"][class*="user"] {
        background-color: #DCF8C6; /* Light green */
        border-radius: 10px 10px 0 10px;
        padding: 10px;
        border: 1px solid #A5D6A7;
        margin-bottom: 10px; margin-left: auto; margin-right: 5px; float: right; clear: both; max-width: 75%;}
    /* Style for assistant messages */
    div[data-testid="stChatMessage"][class*="assistant"] {
        background-color: #FFFFFF; /* White */
        border-radius: 10px 10px 10px 0;
        padding: 10px;
        border: 1px solid #E0E0E0;
        margin-bottom: 10px; margin-left: 5px; margin-right: auto; float: left; clear: both; max-width: 75%;}
    .stChatMessage { overflow: hidden; } /* Contain floats */
    .stChatMessage:after { content: ""; display: table; clear: both; }
    .stCaption { font-size: 0.85em; color: #555; }
    .stExpander { border: none !important; margin-top: -5px; background-color: transparent !important; }
    .stExpander header { font-size: 0.9em; color: #444; padding: 2px 0px !important; }
    .stButton>button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def display_sources(sources):
    """Displays the sources list."""
    if sources:
        # Use 'expanded=False' for less clutter by default
        with st.expander("View Sources", expanded=False):
            st.markdown(f"**Answer derived from ({len(sources)} sources):**")
            for source in sources:
                st.caption(f"- {source}")

def check_backend_status(session_id):
    """Polls the backend status endpoint."""
    if not session_id: return None
    status_url = f"{STATUS_ENDPOINT}/{session_id}"
    try:
        print(f"Frontend: Checking status at {status_url}")
        response = requests.get(status_url, timeout=15) # Slightly longer timeout for status
        response.raise_for_status()
        return response.json() # Expects {"status": "...", "message": "..."}
    except requests.exceptions.Timeout:
        print("Frontend: Status check timed out.")
        return {"status": "timeout", "message": "Status check timed out."}
    except requests.exceptions.RequestException as e:
        print(f"Frontend: Status check failed: {e}")
        status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else 503 # Default to Service Unavailable
        if status_code == 404:
            # It's possible 404 means processing just hasn't created the status entry yet
            print("Frontend: Status check got 404, assuming still processing.")
            return {"status": "processing", "message": "Backend status not found (might be starting)..."}
        else:
             return {"status": "error", "message": f"Failed to check status (Code: {status_code}): {e}"}
    except Exception as e:
         print(f"Frontend: Unexpected error during status check: {e}")
         return {"status": "error", "message": f"Unexpected error checking status: {e}"}

# --- Streamlit App ---
st.title("📄 AI Document Q&A System")
st.markdown("Upload documents (PDF, DOCX, PPTX, XLSX, CSV, JSON, TXT, PNG, JPG). Processing includes OCR & Web Crawling.")

# --- Session State Init ---
# Initialize keys robustly if they don't exist
default_state = {"session_id":None,"processing_complete":False,"upload_status_message":"","upload_status_type":"info","messages":[],"uploaded_file_names":[],"poll_active":False}
for key, default_value in default_state.items():
    if key not in st.session_state: st.session_state[key] = default_value

# --- Sidebar ---
with st.sidebar:
    st.header("Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files",
        accept_multiple_files=True, # Correct keyword arg
        type=["pdf","docx","pptx","xlsx","csv","json","txt","png","jpg","jpeg"], # Correct keyword arg
        key="file_uploader" # Correct keyword arg
    )
    current_file_names = sorted([f.name for f in uploaded_files or []])

    # --- Upload Logic ---
    # This block runs ONLY when the list of uploaded files changes
    if current_file_names != st.session_state.uploaded_file_names:
        print("Frontend: Detected file change in sidebar.")
        # Clear previous session state ONLY if new files are actually selected
        if uploaded_files:
            print(f"Frontend: New files detected ({len(uploaded_files)}). Resetting state.")
            st.session_state.session_id = None
            st.session_state.processing_complete = False
            st.session_state.messages = [] # Clear chat
            st.session_state.upload_status_message = "Initiating upload..."
            st.session_state.upload_status_type = "info"
            st.session_state.poll_active = False # Ensure polling starts fresh
            st.session_state.uploaded_file_names = current_file_names # Store names now

            with st.spinner(f"Uploading {len(uploaded_files)} file(s)..."):
                files_to_send = [("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files]
                upload_success = False
                try:
                    print(f"Frontend: Sending POST to {UPLOAD_ENDPOINT}")
                    response = requests.post(UPLOAD_ENDPOINT, files=files_to_send, timeout=45) # Slightly longer upload timeout
                    response.raise_for_status()
                    result = response.json()
                    print(f"Frontend: Initial upload response: {result}")
                    sid=result.get("session_id"); bs=result.get("status")
                    if sid and bs=="processing":
                        st.session_state.session_id = sid
                        st.session_state.upload_status_message = result.get("message", "✅ Files accepted. Processing started...")
                        st.session_state.upload_status_type = "info"
                        st.session_state.poll_active = True # Enable polling
                        upload_success = True
                        print(f"Frontend: Upload success. Session: {sid}. Poll Active: True")
                    else:
                        raise ValueError(result.get("message", "Upload rejected by backend or invalid status."))
                except Exception as e:
                    st.session_state.upload_status_message = f"❌ Upload Error: {e}"
                    st.session_state.upload_status_type = "error"
                    st.session_state.poll_active = False
                    st.session_state.session_id = None # Ensure no stale session id
                    print(f"Frontend: Upload exception: {e}")

            # *** IMPORTANT: Only rerun if upload was successfully initiated ***
            if upload_success:
                 st.rerun() # Rerun to start the polling process display

        elif not uploaded_files and st.session_state.uploaded_file_names: # Files were removed
             print("Frontend: Files removed. Clearing session.")
             st.session_state.clear() # Clear everything if files are removed
             st.session_state.upload_status_message = "Upload documents to begin."
             st.session_state.upload_status_type = "info"
             st.rerun() # Rerun to reflect cleared state

    # --- Status Display & Polling Logic ---
    # This block runs on every rerun if polling is active
    status_placeholder = st.empty()
    if st.session_state.get('poll_active') and not st.session_state.get('processing_complete'):
        # Display current status message while polling
        with status_placeholder.container():
             msg = st.session_state.get('upload_status_message','Polling status...')
             st_type = st.session_state.get('upload_status_type','info')
             if st_type == "info": st.info(msg, icon="⏳")
             elif st_type == "error": st.error(msg, icon="❌") # Show error if upload failed
             else: st.info(msg) # Fallback

        # Perform status check
        status_result = check_backend_status(st.session_state.get('session_id'))

        if status_result: # Check if status_result is not None
            current_status = status_result.get("status")
            current_message = status_result.get("message")

            # Update status message if backend provides a more specific one
            if current_status == "processing" and current_message and current_message != st.session_state.get('upload_status_message'):
                st.session_state.upload_status_message = current_message # Update displayed message

            # Check for final states
            if current_status == "ready":
                print(f"Frontend: Polling detected 'ready' status.")
                st.session_state.processing_complete = True
                st.session_state.poll_active = False
                st.session_state.upload_status_message = current_message or "✅ Processing complete! Ready for questions."
                st.session_state.upload_status_type = "success"
                status_placeholder.empty() # Clear the placeholder
                st.rerun() # Rerun to show final success and enable chat

            elif current_status == "error":
                 print(f"Frontend: Polling detected 'error' status.")
                 st.session_state.processing_complete = False
                 st.session_state.poll_active = False
                 st.session_state.upload_status_message = f"❌ Processing failed: {current_message or 'Unknown backend error.'}"
                 st.session_state.upload_status_type = "error"
                 status_placeholder.empty()
                 st.rerun() # Rerun to show final error

            elif current_status == "processing":
                 # Still processing, schedule next check
                 print(f"Frontend: Polling status is '{current_status}'. Waiting...")
                 time.sleep(4) # Wait 4 seconds before next check
                 st.rerun() # Trigger next poll cycle

            else: # Handle timeout, not_found, or other unexpected statuses
                 print(f"Frontend: Polling received unexpected status '{current_status}'. Stopping poll.")
                 st.session_state.upload_status_message = f"⚠️ Status Check Issue: {current_message or current_status}"
                 st.session_state.upload_status_type = "warning"
                 st.session_state.poll_active = False
                 status_placeholder.empty()
                 st.rerun()
        else: # check_backend_status returned None (should be rare)
             print(f"Frontend: Status check failed critically. Stopping poll.")
             st.session_state.upload_status_message = "⚠️ Could not retrieve processing status from backend."
             st.session_state.upload_status_type = "warning"
             st.session_state.poll_active = False
             st.rerun()

    # Display final status message if polling is finished
    if not st.session_state.get('poll_active') and st.session_state.get('upload_status_message'):
         # Don't redisplay info message if processing just completed successfully
         if st.session_state.get('upload_status_type') != "success":
             with status_placeholder.container():
                 msg = st.session_state.get('upload_status_message')
                 st_type = st.session_state.get('upload_status_type')
                 if st_type == "error": st.error(msg, icon="❌")
                 elif st_type == "warning": st.warning(msg, icon="⚠️")
                 elif st_type == "info" and not st.session_state.get('processing_complete'): # Only show info if processing didn't finish
                     st.info(msg)


    # Display uploaded files list Expander
    if st.session_state.get('session_id'): # Show if a session exists
        expander_title = "Uploaded Files"
        status_icon = ""
        pc = st.session_state.get('processing_complete', False)
        pa = st.session_state.get('poll_active', False)
        ust = st.session_state.get('upload_status_type', 'info')

        if not pc and pa: expander_title += " (Processing...)"; status_icon="⏳"
        elif pc and ust != 'error': expander_title += " (Ready)"; status_icon="✅"
        elif ust == 'error': expander_title += " (Error)"; status_icon="❌"
        else: expander_title += " (Status Unknown)" # Fallback

        # Default expand state - expand if processing or just finished successfully
        expand_default = pa or ust == 'success'
        with st.expander(f"{status_icon} {expander_title}", expanded=expand_default):
             if st.session_state.get('uploaded_file_names'):
                 for name in st.session_state.uploaded_file_names: st.caption(name)
             else:
                  st.caption("No files currently associated with this session.") # Should only happen after clear


    # Session control button
    st.markdown("---")
    if st.button("Clear Session & Start Over", key="clear"):
        st.session_state.clear() # Clear all session state
        st.rerun() # Rerun to reflect cleared state
    st.markdown("---")
    st.caption(f"Backend API: {BACKEND_URL}")


# --- Chat Interface ---
message_container = st.container() # Use a container for messages
with message_container:
    # Display existing messages from session state
    for msg in st.session_state.get('messages', []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Display sources only for successful assistant messages
            if msg["role"] == "assistant" and msg.get("type") != "error" and msg.get("sources"):
                display_sources(msg.get("sources", []))

# Define chat input - disable based on processing_complete state
prompt = st.chat_input("Ask a question...",
                       disabled=not st.session_state.get('processing_complete', False),
                       key="chat_input")

# Logic to handle prompt submission
if prompt:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt: st.warning("Please enter a question.")
    elif not st.session_state.get('session_id'): st.error("No active session. Please upload documents first.")
    else:
        # Append user message to state
        st.session_state.messages.append({"role": "user", "content": cleaned_prompt, "type": "text"})
        # Trigger a rerun immediately to display the user message
        st.rerun()

# Logic to generate assistant response if the last message was from the user
# This block executes *after* the rerun triggered by submitting the prompt
if st.session_state.get('messages') and st.session_state.messages[-1]["role"] == "user":
    last_user_message = st.session_state.messages[-1]["content"]

    # Use st.chat_message context manager for response display area
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking... ▌") # Initial thinking indicator

        full_response_content = ""
        sources = []
        response_type = "error" # Default to error

        try:
            payload = {"question": last_user_message, "session_id": st.session_state.session_id}
            print(f"Frontend: Sending POST to {ASK_ENDPOINT} for question: {last_user_message}")
            response = requests.post(ASK_ENDPOINT, json=payload, timeout=180) # Long timeout for LLM
            print(f"Frontend: Received ask response status: {response.status_code}")
            response.raise_for_status() # Check for HTTP errors

            result = response.json()
            print(f"Frontend: Raw backend response for /ask: {result}")

            full_response_content = result.get("answer", "Error: Backend did not return an answer.")
            response_type = result.get("type", "error") # Default to error if type missing
            sources = result.get("sources", [])

        except requests.exceptions.Timeout:
            full_response_content = "❌ Error: The backend timed out while generating the answer."; response_type = "error"
        except requests.exceptions.ConnectionError:
            full_response_content = f"❌ Connection Error: Could not connect to the backend at {BACKEND_URL}."; response_type = "error"
        except requests.exceptions.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else 'N/A'
            error_msg = f"❌ Error asking question: {e} (Status: {status_code})"
            try: # Try to get detail from backend response json
                if hasattr(e, 'response') and e.response is not None:
                     error_details = e.response.json().get("detail", e.response.text)
                     error_msg += f"\nBackend Detail: {error_details}"
            except Exception: error_details = "(Could not parse error details)"
            full_response_content = error_msg; response_type = "error"
        except Exception as e: # Catch-all for any other unexpected error
            full_response_content = f"❌ An unexpected frontend error occurred: {e}"; response_type = "error"
            traceback.print_exc() # Log frontend traceback

        # --- Append the final assistant response (or error) to messages state ---
        # This happens regardless of success or failure in the try block above
        st.session_state.messages.append({
            "role": "assistant", "content": full_response_content, "type": response_type,
            "data": None, "chart_data": None, # Not handling specific data types
            "sources": sources if response_type != "error" else []
        })

        # --- Rerun one last time to display the *just added* assistant message ---
        # This is needed because the message is added to state *after* the `with st.chat_message("assistant"):`
        # block has finished executing in this script run.
        st.rerun()