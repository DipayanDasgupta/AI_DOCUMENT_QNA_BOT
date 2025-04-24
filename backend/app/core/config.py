import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Determine project root relative to this file's location
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT_DIR, '.env'),
        env_file_encoding='utf-8',
        case_sensitive=True, # Important for env var names
        extra='ignore'
    )

    PROJECT_NAME: str = "AI Document Q&A Backend"
    API_V1_STR: str = "/api/v1"

    # --- Google Gemini Settings ---
    GEMINI_API_KEY: Optional[str] = None # Will be loaded from .env
    # Common models: gemini-1.5-flash-latest, gemini-pro, gemini-1.0-pro
    GEMINI_MODEL_NAME: str = "gemini-2.5-pro-exp-03-25"

    # --- Storage Paths (relative to project root) ---
    DATA_DIR: str = os.path.join(PROJECT_ROOT_DIR, 'data')
    UPLOAD_DIR: str = os.path.join(DATA_DIR, 'uploaded_files')
    INDEX_DIR: str = os.path.join(DATA_DIR, 'index_store')

    # --- Embedding & Search Settings ---
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    SEARCH_TOP_K: int = 10

    # --- OCR Settings ---
    TESSERACT_CMD: Optional[str] = None

    # --- Crawler Settings ---
    CRAWLER_TIMEOUT: int = 10
    CRAWLER_MAX_DEPTH: int = 0

settings = Settings()

# Create data directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.INDEX_DIR, exist_ok=True)


# Validate Gemini Key
if not settings.GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not set in the environment or .env file.")

# Validate essential settings
if not settings.GEMINI_API_KEY:
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!! WARNING: GEMINI_API_KEY is not set in the environment  !!!")
    print("!!!          or .env file. Gemini LLM calls will fail.     !!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

