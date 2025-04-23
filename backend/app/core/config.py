import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Determine project root relative to this file's location
# config.py -> core -> app -> backend -> PROJECT_ROOT
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT_DIR, '.env'),
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    PROJECT_NAME: str = "AI Document Q&A Backend"
    API_V1_STR: str = "/api/v1"

    # --- OpenAI Settings ---
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-3.5-turbo"

    # --- Storage Paths (relative to project root) ---
    DATA_DIR: str = os.path.join(PROJECT_ROOT_DIR, 'data')
    UPLOAD_DIR: str = os.path.join(DATA_DIR, 'uploaded_files')
    INDEX_DIR: str = os.path.join(DATA_DIR, 'index_store') # Stores FAISS index + mappings

    # --- Embedding & Search Settings ---
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    # EMBEDDING_DEVICE: str = "cuda" # Or "cpu" - Set based on availability
    CHUNK_SIZE: int = 500 # Characters per chunk (adjust as needed)
    CHUNK_OVERLAP: int = 50 # Characters overlap between chunks
    SEARCH_TOP_K: int = 5 # Number of relevant chunks to retrieve

    # --- OCR Settings ---
    TESSERACT_CMD: Optional[str] = None # Set if tesseract isn't in PATH, e.g., '/usr/bin/tesseract'

    # --- Crawler Settings ---
    CRAWLER_TIMEOUT: int = 10 # Seconds to wait for a webpage
    CRAWLER_MAX_DEPTH: int = 0 # 0 means only crawl the linked page, no further links

settings = Settings()

# Create data directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.INDEX_DIR, exist_ok=True)

# Validate essential settings
if not settings.OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY is not set in the environment or .env file. LLM calls will fail.")

