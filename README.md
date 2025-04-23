# AI Document Q&A System (Mando Hackathon)

This project implements an AI-powered question-answering system capable of ingesting documents in various formats, building a knowledge base, and answering user questions based on the content.

## Features

*   **Multi-Format Ingestion:** Supports PDF, DOCX, TXT, PNG, JPG documents. (Support for PPTX, XLSX, CSV, JSON can be added).
*   **OCR Integration:** Extracts text from images (PNG, JPG) and image-based PDFs using Tesseract OCR.
*   **Web Crawling:** Extracts URLs mentioned in documents and crawls the linked web pages (depth 0) to include their text content.
*   **Semantic Search:** Uses Sentence Transformers (`all-MiniLM-L6-v2`) to generate embeddings and FAISS for efficient similarity search to find relevant context even if keywords don't match exactly.
*   **LLM Integration:** Uses OpenAI (GPT-3.5 Turbo by default) to generate natural language answers based on the retrieved context.
*   **Web Interface:** A Streamlit application provides a user-friendly interface for file uploads and asking questions.
*   **Background Processing:** File parsing, crawling, and indexing happen in background tasks for a more responsive UI.

## Project Structure
Use code with caution.
Markdown
mando_hackathon/
├── backend/
│ ├── app/
│ │ ├── api/ # FastAPI endpoints (upload, query)
│ │ ├── core/ # Configuration (settings)
│ │ ├── models/ # Pydantic models (API requests/responses, internal data)
│ │ ├── services/ # Business logic
│ │ │ ├── knowledge/ # Indexing, search, crawling, LLM interface
│ │ │ ├── parser/ # Document parsing, OCR
│ │ │ └── text_splitter.py # Text chunking logic
│ │ └── init.py
│ ├── main.py # FastAPI application entry point
│ └── requirements.txt # Backend Python dependencies
├── data/
│ ├── index_store/ # Stores FAISS index files and mappings (per session)
│ └── uploaded_files/ # Temporary storage for uploaded files during processing
├── frontend/
│ ├── app.py # Streamlit application code
│ └── requirements.txt # Frontend Python dependencies
├── .env # Stores API keys (e.g., OpenAI) - !!! DO NOT COMMIT !!!
├── .gitignore # Files and directories ignored by Git
├── venv/ # Python virtual environment (created by user)
└── README.md # This file
## Setup Instructions

### 1. Prerequisites

*   **Python:** Version 3.10+ recommended.
*   **Git:** For cloning the repository.
*   **Tesseract OCR Engine:** Required for extracting text from images.

### 2. Clone Repository

```bash
git clone <your-repo-url>
cd mando_hackathon
Use code with caution.
3. Create Python Virtual Environment
python3 -m venv venv
source venv/bin/activate # On Windows use `venv\Scripts\activate`
Use code with caution.
Bash
4. Install Python Dependencies
Install requirements for both the backend and the frontend:
# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies
pip install -r frontend/requirements.txt
Use code with caution.
Bash
5. Install System Dependencies (Tesseract)
Ensure the Tesseract OCR engine is installed and accessible in your system's PATH.
Debian/Ubuntu:
sudo apt update && sudo apt install tesseract-ocr
# Optional: sudo apt install tesseract-ocr-eng # For English language pack
Use code with caution.
Bash
macOS (using Homebrew):
brew install tesseract
# Optional: brew install tesseract-lang
Use code with caution.
Bash
Windows: Download an installer (e.g., from UB-Mannheim Tesseract builds on GitHub) and ensure the installation directory is added to your system's PATH.
Verify the installation by running tesseract --version in your terminal.
6. Configure API Key
Create a file named .env in the project root directory (mando_hackathon/.env).
Add your OpenAI API key to this file:
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
Use code with caution.
Env
Replace "sk-..." with your actual key.
Important: The .gitignore file is configured to prevent committing the .env file. Keep your API keys secure.
Running the Application
You need two terminals open, both with the virtual environment activated (source venv/bin/activate).
Terminal 1: Start the Backend Server
Navigate to the project root directory:
cd /path/to/mando_hackathon
Use code with caution.
Bash
Activate the virtual environment:
source venv/bin/activate
Use code with caution.
Bash
Set the PYTHONPATH environment variable:
export PROJECT_ROOT_PATH="$(pwd)"
export BACKEND_PATH="${PROJECT_ROOT_PATH}/backend"
export PYTHONPATH="${PROJECT_ROOT_PATH}:${BACKEND_PATH}:${PYTHONPATH:-}"
Use code with caution.
Bash
Run the Uvicorn server:
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
Use code with caution.
Bash
Keep this terminal running. You should see logs indicating the server has started and loaded the embedding model.
Terminal 2: Start the Frontend Application
Navigate to the project root directory:
cd /path/to/mando_hackathon
Use code with caution.
Bash
Activate the virtual environment:
source venv/bin/activate
Use code with caution.
Bash
Navigate to the frontend directory:
cd frontend
Use code with caution.
Bash
Run the Streamlit application:
streamlit run app.py
Use code with caution.
Bash
Keep this terminal running.
Accessing the Application
Open your web browser and navigate to the URL provided by Streamlit (usually http://localhost:8501).
Usage
Use the sidebar in the web interface to upload one or more supported documents (PDF, DOCX, TXT, PNG, JPG).
Wait for the file processing to complete in the background. Monitor the backend terminal logs for progress (parsing, crawling, indexing). The frontend might show a loading indicator or an initial status message.
Once processing seems complete, type your question about the document content into the chat input box at the bottom and press Enter.
The backend will perform a semantic search, retrieve relevant context, and use the OpenAI LLM to generate an answer based only on that context.
The answer will be displayed in the chat interface.
Technologies Used
Backend: FastAPI, Uvicorn, Pydantic
Frontend: Streamlit
LLM: OpenAI API (GPT-3.5 Turbo default)
Embeddings: Sentence Transformers (all-MiniLM-L6-v2)
Vector Store: FAISS (CPU)
Parsing: PyPDF, python-docx
OCR: Pytesseract (+ Tesseract engine)
Crawling: Requests, BeautifulSoup4
Text Processing: NLTK
Limitations
Persistence: Indexed data (FAISS files, mappings, chunk details) is currently stored locally in the data/ directory but the in-memory CHUNK_DETAIL_STORE is lost when the backend server restarts. A proper database would be needed for persistence.
Scalability: The current setup uses local FAISS and in-memory storage, suitable for moderate use but not large-scale deployment.
Parser Coverage: Only basic parsers for PDF, DOCX, TXT, and Images (OCR) are implemented. Adding robust support for XLSX, PPTX, CSV, JSON requires specific parsing logic.
OCR Accuracy: Tesseract's accuracy depends on image quality and language.
Crawling: Basic depth-0 crawling. More advanced crawling (handling JS, respecting robots.txt) is not implemented.
Error Handling: Basic error handling is present, but could be more robust.
**2. Steps to Restart Backend and Frontend**

Here are the clear steps if you need to stop and restart everything:

**To Restart the Backend:**

1.  Go to the terminal window where the `uvicorn backend.main:app ...` command is running.
2.  Press `Ctrl+C` to stop the server. Wait for it to shut down cleanly (you should see shutdown logs).
3.  Make sure you are still in the **project root directory** (`~/mando_hackathon`).
4.  Make sure the virtual environment is still active (`source venv/bin/activate` if needed).
5.  **Re-export the `PYTHONPATH`** (environment variables are often specific to a shell session):
    ```bash
    export PROJECT_ROOT_PATH="$(pwd)"
    export BACKEND_PATH="${PROJECT_ROOT_PATH}/backend"
    export PYTHONPATH="${PROJECT_ROOT_PATH}:${BACKEND_PATH}:${PYTHONPATH:-}"
    ```
6.  Run the `uvicorn` command again:
    ```bash
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
    ```

**To Restart the Frontend:**

1.  Go to the terminal window where the `streamlit run app.py` command is running.
2.  Press `Ctrl+C` to stop the Streamlit app.
3.  Make sure you are in the **frontend directory** (`~/mando_hackathon/frontend`).
4.  Make sure the virtual environment is still active (`source ../venv/bin/activate` or `source ~/mando_hackathon/venv/bin/activate` if needed).
5.  Run the `streamlit` command again:
    ```bash
    streamlit run app.py
    ```
