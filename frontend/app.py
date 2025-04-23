# PASTE THE ENTIRE CORRECTED PYTHON CODE HERE
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
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/upload" # Corrected endpoint
ASK_ENDPOINT = f"{BACKEND_URL}/api/v1/ask"       # Corrected endpoint

# --- Helper Functions ---

def display_sources(sources):
    """Displays the sources list, possibly in an expander."""
    if sources:
        with st.expander("View Sources", expanded=False):
            for i, source in enumerate(sources):
                st.caption(f"{i+1}. {source}") # Numbered list

# --- Streamlit App ---

st.set_page_config(page_title="AI Document Q&A", layout="wide")
st.title("📄 AI Document Q&A System")
st.markdown("Upload your documents (PDF, DOCX, PPTX, XLSX, CSV, JSON, TXT, PNG, JPG), then ask questions!")

# --- Session State Initialization ---
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "files_ready_for_chat" not in st.session_state:
    # Use a more descriptive state name for enabling chat
    st.session_state.files_ready_for_chat = False
if "messages" not in st.session_state:
    st.session_state.messages = [] # Store chat history {role: "user/assistant", content: "...", type: "text/table/chart/error", data: {...}, sources: [...]}
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
        key="file_uploader" # Use a key to help manage state
    )

    # Check if new files have been uploaded by comparing names
    current_file_names = sorted([f.name for f in uploaded_files]) if uploaded_files else []

    # Detect if files were added OR removed (uploader becomes empty)
    if current_file_names != st.session_state.uploaded_file_names:
        print("Detected file change...") # Debug print
        st.session_state.files_ready_for_chat = False # Reset chat readiness
        st.session_state.messages = [] # Clear chat history
        st.session_state.session_id = None # Reset session ID
        st.session_state.uploaded_file_names = current_file_names # Update the list of names

        if uploaded_files: # Only process if there are actually files now
            with st.spinner(f"Uploading {len(uploaded_files)} file(s)... Please wait."):
                files_to_send = []
                for uploaded_file in uploaded_files:
                    # Read file content into BytesIO object for requests
                    # Using getvalue() is fine for smaller files in Streamlit context
                    files_to_send.append(("files", (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)))

                # --- Corrected try...except block ---
                try:
                    print(f"Sending POST to {UPLOAD_ENDPOINT}") # Debug print
                    response = requests.post(UPLOAD_ENDPOINT, files=files_to_send, timeout=300) # Increased timeout
                    print(f"Received response: {response.status_code}") # Debug print
                    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                    result = response.json()
                    print(f"Backend JSON response: {result}") # Debug print

                    # --- Handle Backend Response ---
                    session_id_received = result.get("session_id")
                    backend_status = result.get("status")
                    backend_message = result.get("message")

                    # Check if we got a session_id and a status indicating processing started
                    if session_id_received and (backend_status == "processing" or backend_status == "success"):
                        st.session_state.session_id = session_id_received
                        st.session_state.files_ready_for_chat = True # Enable chat input
                        # Use the message from backend if available, otherwise provide default
                        info_msg = backend_message or "Files accepted. Processing started in background."
                        st.info(f"⏳ {info_msg} (Session: {st.session_state.session_id}). You can ask questions now.")

                    else: # Handle explicit failure from backend JSON or unexpected response
                        error_message = backend_message or "Unknown error during file processing initiation (Invalid backend response)."
                        st.error(f"❌ File processing initiation failed: {error_message}")
                        # Reset states fully on failure
                        st.session_state.files_ready_for_chat = False
                        st.session_state.uploaded_file_names = []
                        st.session_state.session_id = None

                except requests.exceptions.Timeout:
                     st.error("❌ Upload timed out. The server took too long to respond.")
                     # Reset states fully on failure
                     st.session_state.files_ready_for_chat = False
                     st.session_state.uploaded_file_names = []
                     st.session_state.session_id = None
                except requests.exceptions.ConnectionError:
                     st.error(f"❌ Connection Error: Could not connect to the backend at {BACKEND_URL}. Is the backend running?")
                     # Reset states fully on failure
                     st.session_state.files_ready_for_chat = False
                     st.session_state.uploaded_file_names = []
                     st.session_state.session_id = None
                except requests.exceptions.RequestException as e:
                    # Catch other request errors (like 4xx/5xx handled by raise_for_status)
                    st.error(f"❌ An error occurred during file upload: {e}")
                    try:
                        # Attempt to get more details from the response if available
                        error_details = response.json().get("message", response.text)
                        st.error(f"Backend error details: {error_details}")
                    except Exception:
                        st.error(f"Could not retrieve specific error details. Status code: {response.status_code if 'response' in locals() else 'N/A'}")
                    # Reset states fully on failure
                    st.session_state.files_ready_for_chat = False
                    st.session_state.uploaded_file_names = []
                    st.session_state.session_id = None
                # --- End Corrected try...except block ---

        elif not uploaded_files: # If the uploader is now empty
            st.info("Upload documents to begin.")
            # States already reset above

    # Display status/uploaded files if processing *successfully initiated*
    # files_ready_for_chat is now the gatekeeper for enabling chat
    if st.session_state.files_ready_for_chat:
         # Displaying "Files ready" might be premature as processing is background
         # Maybe just show the uploaded file list
         # st.success("✅ Files ready for Q&A.") # Keep if preferred
         if st.session_state.uploaded_file_names:
             with st.expander("Uploaded Files (Processing Started)"):
                 for name in st.session_state.uploaded_file_names:
                     st.caption(name)

    # Session control button
    st.markdown("---") # Separator
    if st.button("Clear Session & Start Over"):
        st.session_state.session_id = None
        st.session_state.files_ready_for_chat = False # Reset chat readiness too
        st.session_state.messages = []
        st.session_state.uploaded_file_names = []
        # Use rerun to clear widgets and state cleanly
        st.rerun()

    st.markdown("---")
    st.caption(f"Backend API: {BACKEND_URL}")


# --- Chat Interface ---

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Display content based on type
        if message["type"] in ["text", "not_found", "error"]:
            st.markdown(message["content"])
        elif message["type"] == "data_table":
            st.markdown(message["content"]) # Display the introductory text
            if message.get("data") and isinstance(message["data"], dict) and "rows" in message["data"] and "columns" in message["data"]:
                try:
                    df = pd.DataFrame(message["data"]["rows"], columns=message["data"]["columns"])
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(f"Failed to display table: {e}")
                    st.json(message.get("data", "No data found in message")) # Show raw data on error
            else:
                st.error("Received table data in unexpected format.")
                st.json(message.get("data", "No data found in message"))
        elif message["type"] == "data_chart":
            st.markdown(message["content"]) # Display introductory text
            if message.get("data") and isinstance(message["data"], dict):
                try:
                    fig = go.Figure(message["data"])
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Failed to display chart: {e}")
                    st.json(message.get("data", "No data found in message")) # Show raw data on error
            else:
                st.error("Received chart data in unexpected format.")
                st.json(message.get("data", "No data found in message"))

        # Display sources if available (applies to assistant messages)
        if message["role"] == "assistant" and message.get("sources"):
            display_sources(message["sources"])


# Chat input for user query - enabled only if files_ready_for_chat is True
prompt = st.chat_input("Ask a question about the documents...", disabled=not st.session_state.files_ready_for_chat)

if prompt:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        st.warning("Please enter a question.")
    elif not st.session_state.session_id:
        # This check might be redundant if disabled state works, but good failsafe
        st.error("Please upload and process documents first (Session ID missing).")
    else:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": cleaned_prompt, "type": "text"})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(cleaned_prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty() # Placeholder for streaming or final answer
            full_response_content = ""
            sources = []
            response_type = "text" # Default type
            response_data = None # For table/chart data

            with st.spinner("Thinking... Contacting AI and searching documents..."):
                try:
                    payload = {"question": cleaned_prompt, "session_id": st.session_state.session_id}
                    response = requests.post(ASK_ENDPOINT, json=payload, timeout=120) # Timeout for LLM response
                    response.raise_for_status()

                    result = response.json()

                    # --- Process Backend Response ---
                    # Explicitly check for backend signaling an error in its JSON response
                    if result.get("status") == "error" or result.get("type") == "error":
                        full_response_content = f"❌ Error from backend: {result.get('message') or result.get('answer', 'Unknown backend error')}"
                        response_type = "error"
                        message_placeholder.markdown(full_response_content) # Display error directly
                    else:
                        full_response_content = result.get("answer", "No answer provided.")
                        response_type = result.get("type", "text") # Get type from backend
                        sources = result.get("sources", [])
                        # Get table or chart data specifically
                        if response_type == "data_table":
                            response_data = result.get("data")
                        elif response_type == "data_chart":
                             response_data = result.get("chart_data")
                        else:
                             response_data = None # Ensure it's None for text/error/not_found

                        # Display based on type
                        message_placeholder.markdown(full_response_content + "▌") # Initial text placeholder

                        if response_type == "data_table" and response_data:
                             if isinstance(response_data, dict) and "rows" in response_data and "columns" in response_data:
                                try:
                                    df = pd.DataFrame(response_data["rows"], columns=response_data["columns"])
                                    st.dataframe(df, use_container_width=True)
                                except Exception as e:
                                    st.error(f"Failed to display table: {e}")
                                    st.json(response_data)
                             else:
                                st.error("Received table data in unexpected format.")
                                st.json(response_data)
                        elif response_type == "data_chart" and response_data:
                             if isinstance(response_data, dict):
                                try:
                                    fig = go.Figure(response_data)
                                    st.plotly_chart(fig, use_container_width=True)
                                except Exception as e:
                                    st.error(f"Failed to display chart: {e}")
                                    st.json(response_data)
                             else:
                                st.error("Received chart data in unexpected format.")
                                st.json(response_data)

                        # Update placeholder with final text if not handled by data display
                        if response_type not in ["data_table", "data_chart"]:
                            message_placeholder.markdown(full_response_content)

                        # Display sources at the end for non-error messages
                        if response_type != "error":
                            display_sources(sources)

                except requests.exceptions.Timeout:
                    full_response_content = "❌ Error: The request timed out while waiting for the backend response."
                    response_type = "error"
                    message_placeholder.markdown(full_response_content)
                except requests.exceptions.ConnectionError:
                    full_response_content = f"❌ Connection Error: Could not connect to the backend at {BACKEND_URL}."
                    response_type = "error"
                    message_placeholder.markdown(full_response_content)
                except requests.exceptions.RequestException as e:
                    full_response_content = f"❌ An error occurred while asking the question: {e}"
                    response_type = "error"
                    try:
                         # Attempt to get more details from the response if available
                         error_details = response.json().get("message", response.text) # Or "detail"
                         full_response_content += f"\nBackend error details: {error_details}"
                    except Exception: # Catch JSONDecodeError or AttributeError
                        full_response_content += f"\nCould not retrieve specific error details. Status code: {response.status_code if 'response' in locals() else 'N/A'}"
                    message_placeholder.markdown(full_response_content)

            # Add assistant response to chat history AFTER potentially displaying data widgets
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response_content, # Store the main text part
                "type": response_type,
                "data": response_data, # Store the raw data (table/chart)
                "sources": sources
            })