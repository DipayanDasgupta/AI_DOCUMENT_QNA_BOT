# frontend/app.py

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import json
import os
from io import BytesIO

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000") # Default to local backend
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/upload" # Corrected endpoint prefix
ASK_ENDPOINT = f"{BACKEND_URL}/api/v1/ask"       # Corrected endpoint prefix

# --- Set Page Config FIRST ---
# Must be the first Streamlit command executed
st.set_page_config(page_title="AI Document Q&A", layout="wide")

# --- Custom CSS for Aesthetics ---
st.markdown("""
<style>
    /* Style for user messages */
    div[data-testid="stChatMessage"][class*="user"] {
        background-color: #e6f7ff; /* Light blue background */
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #91d5ff;
        margin-bottom: 10px; /* Add space below user message */
    }
    /* Style for assistant messages */
    div[data-testid="stChatMessage"][class*="assistant"] {
        background-color: #f0f0f0; /* Light grey background */
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #d9d9d9;
        margin-bottom: 10px; /* Add space below assistant message */
    }
    /* Smaller font for sources */
    .stCaption {
        font-size: 0.85em;
        color: #555; /* Darker grey */
    }
    /* Style the expander for sources */
    .stExpander {
        border: none !important; /* Remove default border */
        margin-top: -5px; /* Adjust spacing */
    }
    .stExpander header {
        font-size: 0.9em;
        color: #333;
        padding: 2px 0px !important; /* Adjust padding */
    }

</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---

def display_sources(sources):
    """Displays the sources list, possibly in an expander."""
    if sources:
        with st.expander("View Sources", expanded=False):
            st.markdown(f"**Answer derived from ({len(sources)} sources):**")
            for i, source in enumerate(sources):
                st.caption(f"- {source}") # Numbered list


# --- Streamlit App ---
# Title and markdown now come AFTER set_page_config
st.title("📄 AI Document Q&A System")
st.markdown("Upload your documents (PDF, DOCX, PPTX, XLSX, CSV, JSON, TXT, PNG, JPG), then ask questions!")

# --- Session State Initialization ---
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "files_ready_for_chat" not in st.session_state:
    st.session_state.files_ready_for_chat = False
if "upload_status_message" not in st.session_state:
    st.session_state.upload_status_message = ""
if "upload_status_type" not in st.session_state:
    st.session_state.upload_status_type = "info"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_file_names" not in st.session_state:
    st.session_state.uploaded_file_names = []

# --- UI Components ---

# File Uploader and Session Control in the sidebar
with st.sidebar:
    st.header("Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files",
        accept_multiple_files=True,
        type=["pdf", "docx", "pptx", "xlsx", "csv", "json", "txt", "png", "jpg", "jpeg"],
        key="file_uploader"
    )

    current_file_names = sorted([f.name for f in uploaded_files]) if uploaded_files else []

    # --- Upload Logic ---
    if current_file_names != st.session_state.uploaded_file_names:
        print("Frontend: Detected file change...")
        st.session_state.files_ready_for_chat = False
        st.session_state.messages = []
        st.session_state.session_id = None
        st.session_state.uploaded_file_names = current_file_names
        st.session_state.upload_status_message = ""
        st.session_state.upload_status_type = "info"

        if uploaded_files:
            with st.spinner(f"Uploading {len(uploaded_files)} file(s)..."):
                files_to_send = []
                for uploaded_file in uploaded_files:
                    files_to_send.append(("files", (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)))

                try:
                    print(f"Frontend: Sending POST to {UPLOAD_ENDPOINT}")
                    response = requests.post(UPLOAD_ENDPOINT, files=files_to_send, timeout=300)
                    print(f"Frontend: Received response status: {response.status_code}")
                    response.raise_for_status()

                    result = response.json()
                    print(f"Frontend: Backend JSON response: {result}")

                    session_id_received = result.get("session_id")
                    backend_status = result.get("status")
                    backend_message = result.get("message")

                    if session_id_received and (backend_status == "processing"):
                        st.session_state.session_id = session_id_received
                        st.session_state.files_ready_for_chat = True
                        st.session_state.upload_status_message = backend_message or "Files accepted. Processing started..."
                        st.session_state.upload_status_type = "info"
                        print(f"Frontend: Upload successful (processing started). Session: {session_id_received}")
                    else:
                        error_message = backend_message or "Initiation failed (Invalid backend response)."
                        st.session_state.upload_status_message = f"❌ File processing initiation failed: {error_message}"
                        st.session_state.upload_status_type = "error"

                except requests.exceptions.Timeout:
                     st.session_state.upload_status_message = "❌ Upload timed out."
                     st.session_state.upload_status_type = "error"
                     st.session_state.files_ready_for_chat = False; st.session_state.session_id = None
                except requests.exceptions.ConnectionError:
                     st.session_state.upload_status_message = f"❌ Connection Error: Cannot connect to backend at {BACKEND_URL}."
                     st.session_state.upload_status_type = "error"
                     st.session_state.files_ready_for_chat = False; st.session_state.session_id = None
                except requests.exceptions.RequestException as e:
                    error_msg_detail = f"❌ Upload Error: {e}"
                    try: error_details = response.json().get("message", response.text)
                    except Exception: error_details = "(Could not parse error details)"
                    error_msg_detail += f"\nBackend details: {error_details}"
                    error_msg_detail += f"\nStatus code: {response.status_code if 'response' in locals() else 'N/A'}"
                    st.session_state.upload_status_message = error_msg_detail
                    st.session_state.upload_status_type = "error"
                    st.session_state.files_ready_for_chat = False; st.session_state.session_id = None

                # Trigger immediate rerun to display status message
                st.rerun()

        elif not uploaded_files:
            st.session_state.upload_status_message = "Upload documents to begin."
            st.session_state.upload_status_type = "info"

    # --- Display Status & Uploaded Files ---
    if st.session_state.upload_status_message:
        if st.session_state.upload_status_type == "info": st.info(st.session_state.upload_status_message, icon="⏳")
        elif st.session_state.upload_status_type == "success": st.success(st.session_state.upload_status_message, icon="✅")
        else: st.error(st.session_state.upload_status_message, icon="❌")

    if st.session_state.session_id and st.session_state.uploaded_file_names:
        with st.expander("Uploaded Files (Processing Started)", expanded=True):
            for name in st.session_state.uploaded_file_names: st.caption(name)

    # Session control button
    st.markdown("---")
    if st.button("Clear Session & Start Over"):
        st.session_state.session_id = None
        st.session_state.files_ready_for_chat = False
        st.session_state.messages = []
        st.session_state.uploaded_file_names = []
        st.session_state.upload_status_message = ""
        st.session_state.upload_status_type = "info"
        st.rerun()

    st.markdown("---")
    st.caption(f"Backend API: {BACKEND_URL}")


# --- Chat Interface ---
# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["type"] in ["text", "not_found", "error"]:
            st.markdown(message["content"])
        elif message["type"] == "data_table":
             st.markdown(message["content"])
             if message.get("data") and isinstance(message["data"], dict) and "rows" in message["data"] and "columns" in message["data"]:
                 try: df = pd.DataFrame(message["data"]["rows"], columns=message["data"]["columns"]); st.dataframe(df, use_container_width=True)
                 except Exception as e: st.error(f"Table display error: {e}"); st.json(message.get("data"))
             else: st.error("Bad table data format"); st.json(message.get("data"))
        elif message["type"] == "data_chart":
             st.markdown(message["content"])
             if message.get("data") and isinstance(message["data"], dict):
                 try: fig = go.Figure(message["data"]); st.plotly_chart(fig, use_container_width=True)
                 except Exception as e: st.error(f"Chart display error: {e}"); st.json(message.get("data"))
             else: st.error("Bad chart data format"); st.json(message.get("data"))

        if message["role"] == "assistant" and message.get("sources"): display_sources(message["sources"])

# Chat input for user query
prompt = st.chat_input("Ask a question about the documents...", disabled=not st.session_state.files_ready_for_chat)

if prompt:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt: st.warning("Please enter a question.")
    elif not st.session_state.session_id: st.error("Session ID missing. Please upload documents again.")
    else:
        st.session_state.messages.append({"role": "user", "content": cleaned_prompt, "type": "text"})
        with st.chat_message("user"): st.markdown(cleaned_prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty(); message_placeholder.markdown("▌")
            full_response_content = ""; sources = []; response_type = "error"; response_data = None

            with st.spinner("Thinking..."):
                try:
                    payload = {"question": cleaned_prompt, "session_id": st.session_state.session_id}
                    print(f"Frontend: Sending POST to {ASK_ENDPOINT} with payload: {payload}")
                    response = requests.post(ASK_ENDPOINT, json=payload, timeout=180)
                    print(f"Frontend: Received ask response status: {response.status_code}")
                    response.raise_for_status()

                    result = response.json()
                    print(f"Frontend: Raw backend response for /ask:")

                    full_response_content = result.get("answer", "Error: No answer field in response.")
                    response_type = result.get("type", "error")
                    sources = result.get("sources", [])
                    response_data = result.get("data") or result.get("chart_data")

                    message_placeholder.empty() # Clear thinking indicator

                    if response_type in ["text", "not_found", "error"]: st.markdown(full_response_content)
                    elif response_type == "data_table":
                        st.markdown(full_response_content)
                        if response_data and isinstance(response_data, dict) and "rows" in response_data and "columns" in response_data:
                            try: df = pd.DataFrame(response_data["rows"], columns=response_data["columns"]); st.dataframe(df, use_container_width=True)
                            except Exception as e: st.error(f"Table display error: {e}"); st.json(response_data or "Missing data field")
                        else: st.error("Bad table data format"); st.json(response_data or "Missing data field")
                    elif response_type == "data_chart":
                        st.markdown(full_response_content)
                        if response_data and isinstance(response_data, dict):
                            try: fig = go.Figure(response_data); st.plotly_chart(fig, use_container_width=True)
                            except Exception as e: st.error(f"Chart display error: {e}"); st.json(response_data or "Missing data field")
                        else: st.error("Bad chart data format"); st.json(response_data or "Missing data field")
                    else:
                         st.error(f"Received unknown response type from backend: {response_type}"); st.json(result)
                         response_type = "error"

                    if response_type != "error": display_sources(sources)

                except requests.exceptions.Timeout:
                    message_placeholder.error("❌ Error: Backend timed out answering."); response_type = "error"; full_response_content = "Timeout"
                except requests.exceptions.ConnectionError:
                    message_placeholder.error(f"❌ Connection Error to backend."); response_type = "error"; full_response_content = "Connection Error"
                except requests.exceptions.RequestException as e:
                    error_msg = f"❌ Error asking question: {e}"
                    try: error_details = response.json().get("message", response.text); error_msg += f"\nBackend: {error_details}"
                    except Exception: error_msg += f"\nStatus code: {response.status_code if 'response' in locals() else 'N/A'}"
                    message_placeholder.error(error_msg); response_type = "error"; full_response_content = error_msg

            st.session_state.messages.append({
                "role": "assistant", "content": full_response_content, "type": response_type,
                "data": response_data, "sources": sources if response_type != "error" else []
            })
