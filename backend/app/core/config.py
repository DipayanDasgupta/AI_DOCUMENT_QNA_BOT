import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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


    # --- Web Search Settings ---
    TAVILY_API_KEY: Optional[str] = None
    # --- LLM Settings ---
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-2.5-pro-exp-03-25" # Default model

    # --- Storage Paths (relative to project root) ---
    DATA_DIR: str = os.path.join(PROJECT_ROOT_DIR, 'data')
    UPLOAD_DIR: str = os.path.join(DATA_DIR, 'uploaded_files')
    INDEX_DIR: str = os.path.join(DATA_DIR, 'index_store')

    # --- Embedding & Search Settings ---
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    SEARCH_TOP_K: int = 10 # Increased context

    # --- OCR Settings ---
    TESSERACT_CMD: Optional[str] = None

    # --- Crawler Settings ---
    CRAWLER_TIMEOUT: int = 15 # Slightly increased timeout
    CRAWLER_MAX_DEPTH: int = 0 # Only crawl linked page

settings = Settings()

if not settings.TAVILY_API_KEY: print("WARNING: TAVILY_API_KEY not set. Web search disabled.")

# Create data directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.INDEX_DIR, exist_ok=True)

# Validate essential keys
if not settings.GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not set. LLM calls will fail.")

