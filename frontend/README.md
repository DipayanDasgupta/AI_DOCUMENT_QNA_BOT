# frontend/README.md

# AI Document Q&A - Frontend

This directory contains the Streamlit frontend application for the AI Document Q&A system.

## Features

*   Upload multiple documents (PDF, DOCX, PPTX, XLSX, CSV, JSON, TXT, PNG, JPG).
*   Chat interface to ask questions about the uploaded documents.
*   Displays text answers, tables, and charts based on the backend response.
*   Shows sources for the answers provided by the backend.
*   Handles file processing status and errors.

## Setup

1.  **Prerequisites:**
    *   Python 3.8+
    *   `pip` package installer
    *   A running instance of the backend API service.

2.  **Clone the Repository (if you haven't already):**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-url>/frontend
    ```

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Backend URL:**
    The application needs to know where the backend API is running. Set the `BACKEND_URL` environment variable.
    *   **Linux/macOS:**
        ```bash
        export BACKEND_URL="http://<backend_host>:<backend_port>"
        # Example: export BACKEND_URL="http://127.0.0.1:8000"
        ```
    *   **Windows (Command Prompt):**
        ```bash
        set BACKEND_URL="http://<backend_host>:<backend_port>"
        ```
    *   **Windows (PowerShell):**
        ```bash
        $env:BACKEND_URL="http://<backend_host>:<backend_port>"
        ```
    If the environment variable is not set, it will default to `http://127.0.0.1:8000`.

## Running the Application

1.  Make sure the backend API service is running and accessible at the configured `BACKEND_URL`.
2.  Navigate to the `frontend` directory in your terminal.
3.  Run the Streamlit app:
    ```bash
    streamlit run app.py
    ```
4.  Open your web browser and go to the URL provided by Streamlit (usually `http://localhost:8501`).

## Usage

1.  Use the sidebar to upload one or more supported document files.
2.  Wait for the files to be processed (a success message will appear).
3.  Type your question into the chat input box at the bottom of the main page and press Enter.
4.  The answer from the backend will appear in the chat window, potentially including text, tables, charts, and sources.
5.  Ask follow-up questions about the same set of documents. Re-uploading files will start a new session.

## Notes

*   Ensure the backend API endpoints (`/upload`, `/ask`) and their expected request/response formats match the assumptions made in `app.py`. Coordinate closely with the backend team.
*   Timeouts for API calls (`requests.post`) might need adjustment based on backend processing time, especially for large files or complex questions.
*   Error handling is included for common API issues, but robust testing with the actual backend is crucial.