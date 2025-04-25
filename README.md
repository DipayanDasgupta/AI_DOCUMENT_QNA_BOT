# AI Document Q&A System (Mando Hackathon)

This project implements an AI-powered, general-purpose question-answering (Q&A) system capable of ingesting documents in various formats, crawling linked web pages, performing web searches, building a knowledge base, and accurately answering user questions based on the combined information.

## Features Implemented

*   **Multi-Format Ingestion:** Supports PDF (text & image-based via OCR), DOCX, PPTX, TXT, PNG/JPG (via OCR), CSV, XLSX, JSON (basic processing via Pandas summary).
*   **OCR Integration:** Uses Tesseract OCR with OpenCV preprocessing and pdf2image fallback for extracting text from images and scanned PDFs.
*   **Reference Link Crawling:** Extracts URLs from documents and uses Trafilatura to fetch and parse the main content from linked web pages (depth 0).
*   **Web Search Integration (RAG):** Performs live web searches using the Tavily Search API based on the user's question to supplement document/crawled context.
*   **Semantic Search:** Uses Sentence Transformers () and FAISS (local index) for efficient retrieval of relevant text chunks (from documents and crawled pages).
*   **LLM Integration:** Uses Google Gemini (configurable model) to generate answers based on a combined context from documents, crawled pages, and web search results. Prompting emphasizes grounding answers in provided sources.
*   **Structured Data Handling:** Loads CSV/XLSX/JSON using Pandas, generates a textual summary (schema, head), indexes the summary, and instructs the LLM to interpret it.
*   **Async Backend:** Uses FastAPI with background tasks for non-blocking file processing (parsing, crawling, indexing).
*   **Status Polling Frontend:** Streamlit UI polls a backend status endpoint to provide feedback during processing and enables chat only when indexing is complete.
*   **User Interface:** Simple, clean Streamlit interface for file uploads, status viewing, and Q&A interaction.

## Project Structure

```
mando_hackathon/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (upload, query, status)
│   │   ├── core/             # Configuration (settings, state)
│   │   ├── models/           # Pydantic models
│   │   ├── services/         # Business logic modules
│   │   │   ├── knowledge/    # Indexing, search, crawling, LLM, web search
│   │   │   ├── parser/       # Document parsing, OCR
│   │   │   └── text_splitter.py
│   │   └── __init__.py
│   ├── main.py             # FastAPI application entry point
│   └── requirements.txt    # Backend dependencies
├── data/                   # (Ignored by Git)
│   ├── index_store/        # Stores FAISS index files + mappings
│   └── uploaded_files/     # Temporary storage for uploads
├── frontend/
│   ├── app.py              # Streamlit application code
│   └── requirements.txt    # Frontend dependencies
├── .env                    # API keys (Gemini, Tavily) - !!! DO NOT COMMIT !!!
├── .gitignore
├── venv/                   # (Created by user)
└── README.md               # This file
```

## Setup Instructions

### 1. Prerequisites

*   **Python:** 3.10+ recommended.
*   **Git:** For cloning.
*   **System Libraries:**
    *   **Tesseract OCR Engine:** (, ) - For image/PDF OCR.
    *   **Poppler Utilities:** () - Required by  for PDF OCR fallback.

### 2. Clone Repository

```bash
git clone https://github.com/DipayanDasgupta/AI_DOCUMENT_QNA_BOT.git
cd AI_DOCUMENT_QNA_BOT
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
```

### 4. Install System Dependencies

Ensure Tesseract and Poppler are installed on your system.

*   **Debian/Ubuntu:**
    ```bash
    sudo apt update && sudo apt install -y tesseract-ocr tesseract-ocr-eng poppler-utils
    ```
*   **macOS (Homebrew):**
    ```bash
    brew install tesseract poppler
    # Optional: brew install tesseract-lang
    ```
*   **Windows:** Download installers/binaries for Tesseract (UB-Mannheim recommended) and Poppler. Add their respective  directories to your system's PATH environment variable.

Verify installations: tesseract 5.3.4
 leptonica-1.82.0
  libgif 5.2.1 : libjpeg 8d (libjpeg-turbo 2.1.5) : libpng 1.6.43 : libtiff 4.5.1 : zlib 1.3 : libwebp 1.3.2 : libopenjp2 2.5.0
 Found AVX2
 Found AVX
 Found FMA
 Found SSE4.1
 Found OpenMP 201511
 Found libarchive 3.7.2 zlib/1.3 liblzma/5.4.5 bz2lib/1.0.8 liblz4/1.9.4 libzstd/1.5.5
 Found libcurl/8.5.0 OpenSSL/3.0.13 zlib/1.3 brotli/1.1.0 zstd/1.5.5 libidn2/2.3.7 libpsl/0.21.2 (+libidn2/2.3.7) libssh/0.10.6/openssl/zlib nghttp2/1.59.0 librtmp/2.3 OpenLDAP/2.6.7 and  (or similar poppler command).

### 5. Install Python Dependencies

```bash
# Install backend and frontend dependencies
pip install -U pip # Upgrade pip
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
# Download NLTK data needed for text splitting
python -c "import nltk; nltk.download('punkt', quiet=True)"
```

### 6. Configure API Keys

*   Create a file named `.env` in the project root directory (`AI_DOCUMENT_QNA_BOT/.env`).
*   Add your API keys:
    ```env
    # Get from Google AI Studio: https://aistudio.google.com/
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"

    # Get from Tavily: https://tavily.com/
    TAVILY_API_KEY="YOUR_TAVILY_API_KEY_HERE"
    ```
*   Replace placeholders with your actual keys.
*   The `.gitignore` prevents this file from being committed.

## Running the Application

**Important:** Run the backend server **WITHOUT** the `--reload` flag when testing functionality that involves background tasks saving index files, otherwise the server might restart unexpectedly. Use `--reload` only for rapid code changes that don't involve the indexing pipeline.

You need **two separate terminals**, both navigated to the project root (`/AI_DOCUMENT_QNA_BOT`) and with the virtual environment activated (`source venv/bin/activate`).

**Terminal 1: Start Backend Server**

```bash
# Navigate into the backend directory
cd backend

# Run Uvicorn (NO reload for stable background tasks)
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
```
Wait for logs indicating "Uvicorn running on http://0.0.0.0:8000".

**Terminal 2: Start Frontend Application**

```bash
# Navigate into the frontend directory
cd frontend

# Run Streamlit
streamlit run app.py
```

### Accessing the Application

Open your web browser and navigate to the URL provided by Streamlit (usually `http://localhost:8501`).

## Usage

1.  Use the sidebar to upload documents (supports multiple formats).
2.  Wait for the status message in the sidebar to change from "Processing..." (⏳) to "Completed..." (✅). This indicates parsing, crawling (if applicable), and indexing are finished.
3.  The chat input below will become enabled.
4.  Type your question about the content of the uploaded documents or crawled web pages.
5.  The system will retrieve relevant context (from documents and web search via Tavily), generate an answer using Gemini, and display it along with the sources used.

## Technologies Used

*   **Backend:** FastAPI, Uvicorn
*   **Frontend:** Streamlit
*   **LLM:** Google Gemini API
*   **Web Search RAG:** Tavily Search API
*   **Embeddings:** Sentence Transformers
*   **Vector Store:** FAISS (CPU)
*   **Parsing:** PyPDF, python-docx, python-pptx, Pandas
*   **OCR:** Tesseract, OpenCV, pdf2image, Pytesseract
*   **Crawling:** Trafilatura
*   **Text Processing:** NLTK
*   **Core Python Libraries:** asyncio, os, json, etc.

## Limitations & Potential Improvements

*   **State Persistence:** In-memory stores (status, dataframes, chunk details) are lost on backend restart. Implement database storage (e.g., SQLite, PostgreSQL with pgvector, Redis) for persistence.
*   **Scalability:** Local FAISS and processing are suitable for moderate use. For large scale, consider distributed task queues (Celery), cloud-based vector databases (Pinecone, Weaviate), and scalable hosting.
*   **Structured Data Querying:** Relies on LLM interpreting text summaries. Implementing direct Pandas/SQL querying based on question intent would be more powerful but complex.
*   **OCR Accuracy:** Tesseract struggles with complex layouts/handwriting. Cloud Vision APIs offer better accuracy for such cases.
*   **Crawler Robustness:** Basic Trafilatura usage. Could add more sophisticated error handling, respect for robots.txt, JavaScript rendering support (e.g., using Playwright/Selenium).
*   **UI/UX:** Frontend is functional but basic. Could add features like citation highlighting, conversation history management, user feedback.
*   **Security:** Basic setup. Production deployment needs proper security considerations (input validation, rate limiting, authentication if needed).
