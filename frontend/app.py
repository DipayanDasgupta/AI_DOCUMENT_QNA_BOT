# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import json
import os
import time
import traceback # For better error logging in frontend
import re # For URL checking

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/upload"
ASK_ENDPOINT = f"{BACKEND_URL}/api/v1/ask"
STATUS_ENDPOINT = f"{BACKEND_URL}/api/v1/status"

# --- Set Page Config FIRST ---
st.set_page_config(page_title="Mando AI Document Q&A", layout="wide", initial_sidebar_state="expanded")

# --- Custom CSS ---
# Using a more compact way to include CSS
st.markdown("""
<style>
    /* Style for user messages */
    div[data-testid="stChatMessage"][class*="user"] { background-color: #DCF8C6; border-radius: 10px 10px 0 10px; padding: 10px; border: 1px solid #A5D6A7; margin-bottom: 10px; margin-left: auto; margin-right: 5px; float: right; clear: both; max-width: 75%;}
    /* Style for assistant messages */
    div[data-testid="stChatMessage"][class*="assistant"] { background-color: #FFFFFF; border-radius: 10px 10px 10px 0; padding: 10px; border: 1px solid #E0E0E0; margin-bottom: 10px; margin-left: 5px; margin-right: auto; float: left; clear: both; max-width: 75%;}
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
    """Displays the sources list, making URLs clickable."""
    if sources:
        with st.expander("View Sources", expanded=False): # Start collapsed
            st.markdown(f"**Sources ({len(sources)}):**")
            for source in sources:
                # Check if the source looks like a URL
                if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://")):
                     st.caption(f"- [{source}]({source})") # Clickable link
                else:
                     st.caption(f"- {source}") # Display non-URLs normally

def check_backend_status(session_id):
    """Polls the backend status endpoint."""
    if not session_id: return None
    status_url = f"{STATUS_ENDPOINT}/{session_id}"
    try:
        print(f"Frontend: Checking status at {status_url}")
        response = requests.get(status_url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Frontend: Status check timed out.")
        return {"status": "timeout", "message": "Status check timed out."}
    except requests.exceptions.RequestException as e:
        print(f"Frontend: Status check failed: {e}")
        status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else 503
        if status_code == 404:
             print("Frontend: Status check got 404, assuming still processing.")
             return {"status": "processing", "message": "Backend status not found (might be starting)..."} # Treat 404 as processing
        else:
             return {"status": "error", "message": f"Status check failed (Code: {status_code}): {e}"}
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
    if current_file_names != st.session_state.uploaded_file_names:
        print("Frontend: Detected file change in sidebar.")
        # --- Reset state logic ---
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

            upload_api_result = None
            upload_error = None
            with st.spinner(f"Uploading {len(uploaded_files)} file(s)..."):
                files_to_send=[("files",(f.name,f.getvalue(),f.type)) for f in uploaded_files]
                try:
                    response = requests.post(UPLOAD_ENDPOINT, files=files_to_send, timeout=45)
                    response.raise_for_status()
                    upload_api_result = response.json()
                    print(f"Frontend: Initial upload response: {upload_api_result}")
                except Exception as e:
                    upload_error = e
                    print(f"Frontend: Upload exception: {e}")

            # --- Process API Result / Error *AFTER* Spinner ---
            if upload_api_result:
                sid=upload_api_result.get("session_id"); bs=upload_api_result.get("status")
                if sid and bs=="processing":
                    st.session_state.session_id = sid
                    st.session_state.upload_status_message = upload_api_result.get("message","✅ Files accepted. Processing started...")
                    st.session_state.upload_status_type = "info"
                    st.session_state.poll_active = True # *** Enable polling ***
                    print(f"Frontend: Upload success. Session: {sid}. Poll Active: True")
                else:
                    st.session_state.upload_status_message = f"❌ Upload Error: {upload_api_result.get('message','Backend issue')}"
                    st.session_state.upload_status_type = "error"
                    st.session_state.poll_active = False
                    st.session_state.session_id = None
            elif upload_error:
                 st.session_state.upload_status_message = f"❌ Upload Request Error: {upload_error}"
                 st.session_state.upload_status_type = "error"
                 st.session_state.poll_active = False
                 st.session_state.session_id = None

            # Rerun ONLY AFTER processing the upload response and setting state
            st.rerun()

        elif not uploaded_files and st.session_state.uploaded_file_names: # Files were removed
             print("Frontend: Files removed. Clearing session.")
             st.session_state.clear() # Clear everything if files are removed
             st.session_state.upload_status_message = "Upload documents to begin." # Reset message
             st.session_state.upload_status_type = "info"
             st.rerun() # Rerun to reflect cleared state


    # --- Status Display & Polling Logic ---
    # This block runs on every script run if polling is active
    status_placeholder = st.empty()
    if st.session_state.get('poll_active') and not st.session_state.get('processing_complete'):
        # Display current status message while polling
        with status_placeholder.container():
             msg = st.session_state.get('upload_status_message','Polling status...')
             st_type = st.session_state.get('upload_status_type','info')
             st.info(msg,icon="⏳") if st_type == "info" else st.error(msg,icon="❌")

        # Perform status check
        status_result = check_backend_status(st.session_state.get('session_id'))

        # --- Process Status Result - CORRECTED INDENTATION ---
        if status_result: # Check if status_result is not None
            current_status = status_result.get("status")
            current_message = status_result.get("message")

            # Update status message if backend provides a more specific one during processing
            if current_status == "processing" and current_message and current_message != st.session_state.get('upload_status_message'):
                st.session_state.upload_status_message = current_message

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
                 time.sleep(3) # Wait 3 seconds before next check
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
             st.rerun() # Stop polling
        # --- END CORRECTED INDENTATION BLOCK ---


    # Display final status message if polling is finished
    if not st.session_state.get('poll_active') and st.session_state.get('upload_status_message'):
         with status_placeholder.container():
             msg = st.session_state.get('upload_status_message')
             st_type = st.session_state.get('upload_status_type')
             if st_type == "success": st.success(msg, icon="✅")
             elif st_type == "error": st.error(msg, icon="❌")
             elif st_type == "warning": st.warning(msg, icon="⚠️")
             elif st_type == "info" and st.session_state.get('processing_complete'): # Show success if polling stopped but processing is done
                 st.success(msg.replace("Processing started...","Processing complete!"), icon="✅")


    # Display uploaded files list Expander
    if st.session_state.get('session_id'): # Show expander only if a session is active
        expander_title = "Uploaded Files"; status_icon = ""
        pc = st.session_state.get('processing_complete', False); pa = st.session_state.get('poll_active', False); ust = st.session_state.get('upload_status_type', 'info')
        if not pc and pa: expander_title += " (Processing...)"; status_icon="⏳"
        elif pc and ust != 'error': expander_title += " (Ready)"; status_icon="✅"
        elif ust == 'error': expander_title += " (Error)"; status_icon="❌"
        expand_default = pa or ust == 'success'
        with st.expander(f"{status_icon} {expander_title}", expanded=expand_default):
             uploaded_file_list = st.session_state.get('uploaded_file_names', [])
             if uploaded_file_list:
                 # --- Corrected Loop ---
                 for name in uploaded_file_list:
                     st.caption(name)
                 # --- END Correction ---
             else:
                  st.caption("No files associated with this session.")

    # --- Clear Button ---
    st.markdown("---");
    if st.button("Clear Session & Start Over",key="clear"): st.session_state.clear(); st.rerun()
    st.markdown("---"); st.caption(f"Backend API: {BACKEND_URL}")

# --- Chat Interface ---
message_container = st.container() # Use a container for messages
with message_container:
    # Display existing messages from session state
    for msg in st.session_state.get('messages',[]):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"]=="assistant" and msg.get("type") != "error" and msg.get("sources"):
                display_sources(msg.get("sources",[]))

# Define chat input - disable based on processing_complete state
prompt = st.chat_input("Ask a question...",
                       disabled=not st.session_state.get('processing_complete', False),
                       key="chat_input")

# Logic to handle prompt submission
if prompt:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt: st.warning("Enter question.")
    elif not st.session_state.get('session_id'): st.error("No session.")
    else: st.session_state.messages.append({"role":"user","content":cleaned_prompt,"type":"text"}); st.rerun()

# Logic to generate assistant response if the last message was from the user
if st.session_state.get('messages') and st.session_state.messages[-1]["role"] == "user":
    last_user_message = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        mp = st.empty(); mp.markdown("Thinking... ▌"); fc = ""; srcs = []; rt = "error"
        try:
            pld={"question":last_user_message,"session_id":st.session_state.session_id}; r=requests.post(ASK_ENDPOINT,json=pld,timeout=180); r.raise_for_status(); res=r.json()
            fc=res.get("answer","Error"); rt=res.get("type","error"); srcs=res.get("sources",[])
        except Exception as e:
            sc="N/A"; ed="(No details)"
            if 'r' in locals() and hasattr(r, 'status_code'): sc=r.status_code;
            try: ed=r.json().get("detail",r.text)
            except: pass
            fc=f"❌ Ask Error: {e}\nBE:{ed}\nStatus:{sc}"; rt="error"
        # Append message state *before* displaying it fully
        st.session_state.messages.append({"role":"assistant","content":fc,"type":rt,"sources":srcs if rt!="error" else []})
        # Now update the placeholder with the final content
        mp.empty() # Clear thinking indicator
        st.markdown(fc)
        if rt != "error": display_sources(srcs)
        # No rerun needed here as we displayed manually after appending state